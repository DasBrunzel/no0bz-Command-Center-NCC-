using System.ComponentModel;
using System.Diagnostics;
using System.Drawing;
using System.Runtime.InteropServices;
using System.ServiceProcess;
using System.Security.Principal;
using System.Text.Json;
using System.Windows.Forms;

namespace NccTray;

internal sealed record TraySettings(string ServerUrl, string Version);
internal sealed record AgentStatus(string? Version, string? Health, DateTimeOffset? LastCheckUtc, string? UpdateStatus);

internal static class Program
{
    private const string ServiceName = "NccAgentCore";
    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool DestroyIcon(IntPtr icon);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    private static extern int RegisterApplicationRestart(string? commandLine, uint flags);

    private static Icon CreateNccIcon()
    {
        using var bitmap = new Bitmap(32, 32);
        using (var graphics = Graphics.FromImage(bitmap))
        {
            graphics.Clear(Color.Transparent);
            graphics.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
            using var background = new SolidBrush(Color.FromArgb(10, 24, 31));
            using var signal = new SolidBrush(Color.FromArgb(111, 226, 189));
            graphics.FillEllipse(background, 1, 1, 30, 30);
            graphics.FillRectangle(signal, 7, 19, 4, 6);
            graphics.FillRectangle(signal, 14, 13, 4, 12);
            graphics.FillRectangle(signal, 21, 7, 4, 18);
        }
        var handle = bitmap.GetHicon();
        try { using var icon = Icon.FromHandle(handle); return (Icon)icon.Clone(); }
        finally { DestroyIcon(handle); }
    }

    [STAThread]
    private static void Main()
    {
        // The SID scopes the global mutex to one user, including multiple
        // interactive sessions of that same Windows account.
        var sid = WindowsIdentity.GetCurrent().User?.Value ?? Environment.UserName;
        Mutex singleton;
        bool created;
        try { singleton = new Mutex(true, @"Global\no0bz-NccTray-" + sid, out created); }
        catch (UnauthorizedAccessException) { return; }
        using (singleton)
        {
            if (!created) return;

            ApplicationConfiguration.Initialize();
            // Inno Setup's Restart Manager can relaunch the tray in the same user
            // session after a silent in-place upgrade.
            RegisterApplicationRestart("", 0);
            Application.Run(new TrayContext(ReadSettings()));
        }
    }

    private static TraySettings ReadSettings()
    {
        var path = Path.Combine(AppContext.BaseDirectory, "tray-settings.json");
        try
        {
            var settings = JsonSerializer.Deserialize<TraySettings>(File.ReadAllText(path),
                new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
            if (settings is not null && Uri.TryCreate(settings.ServerUrl, UriKind.Absolute, out var uri)
                && (uri.Scheme == Uri.UriSchemeHttps || uri.Scheme == Uri.UriSchemeHttp))
                return settings;
        }
        catch (IOException) { }
        catch (JsonException) { }
        catch (UnauthorizedAccessException) { }
        return new TraySettings("", typeof(Program).Assembly.GetName().Version?.ToString() ?? "unbekannt");
    }

    private static AgentStatus? ReadAgentStatus()
    {
        try
        {
            return JsonSerializer.Deserialize<AgentStatus>(
                File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "agent-status.json")),
                new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
        }
        catch (IOException) { return null; }
        catch (JsonException) { return null; }
        catch (UnauthorizedAccessException) { return null; }
    }

    private sealed class TrayContext : ApplicationContext
    {
        private readonly NotifyIcon _icon;
        private readonly Icon _brandIcon;
        private readonly ToolStripMenuItem _dashboard;
        private readonly System.Windows.Forms.Timer _timer;
        private readonly TraySettings _settings;
        private bool _stopping;

        internal TrayContext(TraySettings settings)
        {
            _settings = settings;
            _dashboard = new ToolStripMenuItem("Dashboard öffnen", null, OpenDashboard);
            var exit = new ToolStripMenuItem("Beenden", null, StopAndExit);
            var menu = new ContextMenuStrip();
            menu.Items.Add(_dashboard);
            menu.Items.Add(new ToolStripSeparator());
            menu.Items.Add(exit);
            _brandIcon = CreateNccIcon();
            _icon = new NotifyIcon
            {
                Icon = _brandIcon,
                Text = "NCC Agent",
                ContextMenuStrip = menu,
                Visible = true,
            };
            _icon.DoubleClick += OpenDashboard;

            // A manual stop lasts only until the next interactive sign-in or
            // actual service boot. This also covers Windows Fast Startup.
            TryStartService();
            RefreshStatus();
            _timer = new System.Windows.Forms.Timer { Interval = 5000 };
            _timer.Tick += (_, _) => RefreshStatus();
            _timer.Start();
        }

        private static ServiceController? OpenService()
        {
            try { return new ServiceController(ServiceName); }
            catch (InvalidOperationException) { return null; }
            catch (Win32Exception) { return null; }
        }

        private void TryStartService()
        {
            using var service = OpenService();
            if (service is null) return;
            try
            {
                service.Refresh();
                if (service.Status == ServiceControllerStatus.Stopped) service.Start();
            }
            catch (InvalidOperationException) { }
            catch (Win32Exception) { }
        }

        private void RefreshStatus()
        {
            if (_stopping) return;
            using var service = OpenService();
            bool running;
            try
            {
                service?.Refresh();
                running = service?.Status == ServiceControllerStatus.Running;
            }
            catch (InvalidOperationException) { running = false; }
            catch (Win32Exception) { running = false; }

            var state = ReadAgentStatus();
            var version = state?.Version ?? _settings.Version;
            var checkedAt = state?.LastCheckUtc?.ToLocalTime().ToString("dd.MM HH:mm") ?? "nie";
            var update = state?.UpdateStatus ?? "unbekannt";
            var summary = $"NCC {version} | {(running ? "läuft" : "gestoppt")} | {update} | {checkedAt}";
            _icon.Text = summary.Length <= 63 ? summary : summary[..63];
            // Opening the remote dashboard after the agent has been stopped
            // would misleadingly suggest the local agent is still active.
            _dashboard.Enabled = running && !string.IsNullOrWhiteSpace(_settings.ServerUrl);
        }

        private void OpenDashboard(object? sender, EventArgs e)
        {
            if (!_dashboard.Enabled) return;
            Process.Start(new ProcessStartInfo(_settings.ServerUrl) { UseShellExecute = true });
        }

        private void StopAndExit(object? sender, EventArgs e)
        {
            if (MessageBox.Show(
                    "NCC Agent wirklich beenden? Der Dienst ist danach nicht mehr aktiv.",
                    "NCC Agent", MessageBoxButtons.YesNo, MessageBoxIcon.Warning)
                != DialogResult.Yes) return;

            _stopping = true;
            using var service = OpenService();
            try
            {
                service?.Refresh();
                if (service?.Status == ServiceControllerStatus.Running)
                {
                    service.Stop();
                    service.WaitForStatus(ServiceControllerStatus.Stopped, TimeSpan.FromSeconds(30));
                }
            }
            catch (Exception error) when (error is Win32Exception or InvalidOperationException or System.ServiceProcess.TimeoutException)
            {
                _stopping = false;
                MessageBox.Show($"NCC Agent konnte nicht beendet werden: {error.Message}",
                    "NCC Agent", MessageBoxButtons.OK, MessageBoxIcon.Error);
                RefreshStatus();
                return;
            }
            ExitThread();
        }

        protected override void ExitThreadCore()
        {
            _timer.Stop();
            _timer.Dispose();
            _icon.Visible = false;
            _icon.Dispose();
            _brandIcon.Dispose();
            base.ExitThreadCore();
        }
    }
}
