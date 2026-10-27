using System.Diagnostics;
using System.ServiceProcess;
using System.Text.Json;

namespace NccServiceHost;

internal static class Program
{
    private static void Main(string[] args)
    {
        if (args.Contains("--console", StringComparer.OrdinalIgnoreCase))
        {
            using var host = new CoreService();
            host.StartInteractive();
            Console.CancelKeyPress += (_, eventArgs) => { eventArgs.Cancel = true; host.Stop(); };
            while (host.IsRunning) Thread.Sleep(250);
            return;
        }
        ServiceBase.Run(new CoreService());
    }
}

internal sealed class CoreService : ServiceBase
{
    private readonly object _gate = new();
    private static readonly object LogGate = new();
    private volatile Process? _core;
    private System.Threading.Timer? _updateTimer;
    private volatile bool _stopping;
    internal bool IsRunning { get; private set; }

    internal CoreService()
    {
        ServiceName = "NccAgentCore";
        CanStop = true;
        AutoLog = true;
    }

    internal void StartInteractive() => OnStart([]);

    protected override void OnStart(string[] args)
    {
        lock (_gate)
        {
            _stopping = false;
            StartCore();
            IsRunning = true;
            // Core verifies the approved signed release on every service start.
            // A controlled restart supplies the required periodic update check.
            _updateTimer = new System.Threading.Timer(_ => RestartForUpdate(), null,
                TimeSpan.FromHours(6), TimeSpan.FromHours(6));
        }
    }

    private static string Root => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "no0bz", "NCC Agent");

    private static void Log(string message)
    {
        lock (LogGate)
        {
            try
            {
                var path = Path.Combine(Root, "logs", "service-host.log");
                Directory.CreateDirectory(Path.GetDirectoryName(path)!);
                File.AppendAllText(path, $"{DateTimeOffset.Now:O} {message}{Environment.NewLine}");
            }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }

    private static Dictionary<string, string> ReadConfig()
    {
        var path = Path.Combine(Root, "config", "core.env");
        var result = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var raw in File.ReadLines(path))
        {
            var line = raw.Trim();
            if (line.Length == 0 || line.StartsWith('#')) continue;
            var split = line.IndexOf('=');
            if (split <= 0) throw new InvalidDataException("Invalid core.env entry");
            var value = line[(split + 1)..].Trim();
            if (value.Length >= 2 && value[0] == value[^1] && value[0] is '"' or '\'')
                value = value[1..^1].Replace("\\\"", "\"").Replace("\\\\", "\\");
            result[line[..split].Trim()] = value;
        }
        // A fresh agent receives its bearer token only after browser pairing.
        // Keep the token in the protected credential file and supply it to Core
        // on the next restart, when the signed update check is performed.
        if (!result.ContainsKey("NCC_AGENT_TOKEN") && result.TryGetValue("NCC_AGENT_DATA_DIR", out var dataDir))
        {
            var credential = Path.Combine(dataDir, "agent-credential.json");
            try
            {
                using var json = JsonDocument.Parse(File.ReadAllText(credential));
                if (json.RootElement.TryGetProperty("token", out var token))
                {
                    var value = token.GetString();
                    if (!string.IsNullOrWhiteSpace(value)) result["NCC_AGENT_TOKEN"] = value;
                }
            }
            catch (IOException) { }
            catch (JsonException) { }
            catch (UnauthorizedAccessException) { }
        }
        return result;
    }

    private void StartCore()
    {
        var binary = Path.Combine(AppContext.BaseDirectory, "ncc-core.exe");
        var info = new ProcessStartInfo(binary, "service")
        {
            WorkingDirectory = Path.GetDirectoryName(binary)!,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };
        foreach (var (key, value) in ReadConfig()) info.Environment[key] = value;
        var process = new Process { StartInfo = info, EnableRaisingEvents = true };
        process.OutputDataReceived += (_, e) => { if (e.Data is not null) Log($"core: {e.Data}"); };
        process.ErrorDataReceived += (_, e) => { if (e.Data is not null) Log($"core error: {e.Data}"); };
        process.Exited += (_, _) =>
        {
            if (!_stopping && ReferenceEquals(process, _core))
            {
                Log($"Core exited unexpectedly with code {process.ExitCode}");
                // Exit abnormally so SCM recovery restarts a crashed agent.
                Environment.FailFast("NCC Core exited unexpectedly");
            }
        };
        _core = process;
        try
        {
            if (!process.Start()) throw new InvalidOperationException("Could not start NCC Core");
        }
        catch
        {
            _core = null;
            process.Dispose();
            throw;
        }
        process.BeginOutputReadLine();
        process.BeginErrorReadLine();
        Log($"Started Core process {process.Id}");
    }

    private void RestartForUpdate()
    {
        lock (_gate)
        {
            if (_stopping) return;
            try
            {
                StopCore();
                StartCore();
                Log("Scheduled signed release check started");
            }
            catch (Exception error)
            {
                Log($"Scheduled restart failed: {error.GetType().Name}: {error.Message}");
                Environment.FailFast("NCC Core scheduled restart failed", error);
            }
        }
    }

    private void StopCore()
    {
        var process = _core;
        _core = null;
        if (process is null) return;
        try
        {
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
                if (!process.WaitForExit(20_000)) Log("Core stop timed out");
            }
        }
        catch (InvalidOperationException) { }
        finally { process.Dispose(); }
    }

    protected override void OnStop()
    {
        lock (_gate)
        {
            _stopping = true;
            _updateTimer?.Dispose();
            _updateTimer = null;
            StopCore();
            IsRunning = false;
            Log("Core stopped by SCM");
        }
    }
}
