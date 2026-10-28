using System.Diagnostics;
using System.Net.Http;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace NccServiceHost;

internal sealed record InstallerRelease(
    int SchemaVersion,
    string Version,
    string ArtifactUrl,
    string Sha256,
    long SizeBytes,
    string SignatureKeyId,
    string SignatureValue);

internal static class InstallerUpdater
{
    private const long MaximumInstallerBytes = 1024L * 1024 * 1024;
    private static readonly Regex VersionPattern = new(
        @"^(\d+)\.(\d+)\.(\d+)-(alpha|beta|rc)\.(\d+)(?:-dev\.(\d+))?$",
        RegexOptions.CultureInvariant | RegexOptions.Compiled);

    internal static bool CheckAndLaunch(
        string root,
        string appDir,
        IReadOnlyDictionary<string, string> config,
        Action<string> log,
        CancellationToken cancellationToken)
    {
        if (!config.TryGetValue("NCC_AGENT_INSTALLER_FEED_URL", out var feedUrl)
            || string.IsNullOrWhiteSpace(feedUrl)) return false;
        if (!TryHttpsUrl(feedUrl, out var feedUri))
        {
            log("Installer feed URL rejected: HTTPS is required");
            return false;
        }
        try
        {
            using var client = new HttpClient(new HttpClientHandler
                { AllowAutoRedirect = true, UseProxy = !feedUri.IsLoopback })
            { Timeout = TimeSpan.FromMinutes(10) };
            using var feedResponse = client.GetAsync(feedUri, HttpCompletionOption.ResponseHeadersRead, cancellationToken)
                .GetAwaiter().GetResult();
            feedResponse.EnsureSuccessStatusCode();
            if (feedResponse.RequestMessage?.RequestUri?.Scheme != Uri.UriSchemeHttps)
                throw new InvalidDataException("Installer feed redirected away from HTTPS");
            if (feedResponse.Content.Headers.ContentLength is > 65536)
                throw new InvalidDataException("Installer feed is too large");
            using var feedStream = feedResponse.Content.ReadAsStream();
            using var feedBuffer = new MemoryStream();
            CopyBounded(feedStream, feedBuffer, 65536, cancellationToken);
            var release = JsonSerializer.Deserialize<InstallerRelease>(feedBuffer.ToArray(),
                new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
            if (release is null) return false;
            if (release.SchemaVersion != 1 ||
                string.IsNullOrWhiteSpace(release.Version) ||
                !TryHttpsUrl(release.ArtifactUrl, out var artifactUri) ||
                release.SizeBytes is <= 0 or > MaximumInstallerBytes ||
                !Regex.IsMatch(release.Sha256 ?? "", "^[0-9a-fA-F]{64}$") ||
                string.IsNullOrWhiteSpace(release.SignatureKeyId) ||
                string.IsNullOrWhiteSpace(release.SignatureValue))
                throw new InvalidDataException("Installer feed metadata is invalid");

            var installed = File.ReadAllText(Path.Combine(appDir, "installer-version.txt")).Trim();
            if (CompareVersions(release.Version, installed) <= 0) return false;
            var downloads = Path.Combine(root, "downloads");
            Directory.CreateDirectory(downloads);
            var setup = Path.Combine(downloads, "ncc-agent-setup-" + release.Version + ".exe");
            var temporary = setup + ".tmp";
            using (var response = client.GetAsync(artifactUri, HttpCompletionOption.ResponseHeadersRead, cancellationToken)
                       .GetAwaiter().GetResult())
            {
                response.EnsureSuccessStatusCode();
                if (response.RequestMessage?.RequestUri?.Scheme != Uri.UriSchemeHttps)
                    throw new InvalidDataException("Installer download redirected away from HTTPS");
                if (response.Content.Headers.ContentLength is > MaximumInstallerBytes)
                    throw new InvalidDataException("Installer download is too large");
                using var input = response.Content.ReadAsStream();
                using var output = new FileStream(temporary, FileMode.Create, FileAccess.Write, FileShare.None);
                CopyBounded(input, output, MaximumInstallerBytes, cancellationToken);
            }
            File.Move(temporary, setup, true);
            var core = Path.Combine(appDir, "ncc-core.exe");
            var verifier = new ProcessStartInfo(core)
            {
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardError = true,
            };
            foreach (var value in new[] {
                "--state-dir", Path.Combine(root, "core-state"), "verify-installer",
                "--source", setup, "--version", release.Version,
                "--sha256", release.Sha256!, "--size", release.SizeBytes.ToString(),
                "--url", release.ArtifactUrl, "--key-id", release.SignatureKeyId,
                "--signature", release.SignatureValue,
            }) verifier.ArgumentList.Add(value);
            using var check = Process.Start(verifier) ?? throw new IOException("Could not launch NCC signature verifier");
            var verificationError = check.StandardError.ReadToEnd();
            if (!check.WaitForExit(120_000) || check.ExitCode != 0)
                throw new InvalidDataException("Installer signature verification failed: " + verificationError.Trim());
            cancellationToken.ThrowIfCancellationRequested();
            var launch = new ProcessStartInfo(setup)
            {
                UseShellExecute = false,
                CreateNoWindow = true,
            };
            foreach (var argument in new[] { "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS" })
                launch.ArgumentList.Add(argument);
            using var installer = Process.Start(launch) ?? throw new IOException("Could not launch signed NCC installer");
            log($"Signed NCC Agent installer {release.Version} launched as process {installer.Id}");
            return true;
        }
        catch (Exception error) when (error is IOException or HttpRequestException or OperationCanceledException
            or JsonException or InvalidDataException or System.ComponentModel.Win32Exception or UnauthorizedAccessException)
        {
            log($"Installer update skipped: {error.GetType().Name}: {error.Message}");
            return false;
        }
    }

    private static void CopyBounded(Stream input, Stream output, long limit, CancellationToken cancellationToken)
    {
        var buffer = new byte[128 * 1024];
        long total = 0;
        int count;
        while ((count = input.ReadAsync(buffer, cancellationToken).GetAwaiter().GetResult()) > 0)
        {
            total += count;
            if (total > limit) throw new InvalidDataException("Response exceeds the allowed size");
            output.Write(buffer, 0, count);
        }
    }

    private static bool TryHttpsUrl(string value, out Uri uri)
    {
        if (Uri.TryCreate(value, UriKind.Absolute, out var parsed) &&
            parsed.Scheme == Uri.UriSchemeHttps && string.IsNullOrEmpty(parsed.UserInfo) &&
            string.IsNullOrEmpty(parsed.Fragment))
        {
            uri = parsed;
            return true;
        }
        uri = null!;
        return false;
    }

    internal static int CompareVersions(string left, string right)
    {
        var l = VersionPattern.Match(left);
        var r = VersionPattern.Match(right);
        if (!l.Success || !r.Success) throw new InvalidDataException("Installer version is invalid");
        static int Phase(string value) => value switch { "alpha" => 0, "beta" => 1, "rc" => 2, _ => -1 };
        static long Number(Group group) => long.TryParse(group.Value, out var number)
            ? number : throw new InvalidDataException("Installer version number is invalid");
        var a = new[] { Number(l.Groups[1]), Number(l.Groups[2]), Number(l.Groups[3]),
            Phase(l.Groups[4].Value), Number(l.Groups[5]), l.Groups[6].Success ? -1 : 0,
            l.Groups[6].Success ? Number(l.Groups[6]) : 0 };
        var b = new[] { Number(r.Groups[1]), Number(r.Groups[2]), Number(r.Groups[3]),
            Phase(r.Groups[4].Value), Number(r.Groups[5]), r.Groups[6].Success ? -1 : 0,
            r.Groups[6].Success ? Number(r.Groups[6]) : 0 };
        for (var i = 0; i < a.Length; i++)
        {
            var comparison = a[i].CompareTo(b[i]);
            if (comparison != 0) return comparison;
        }
        return 0;
    }
}
