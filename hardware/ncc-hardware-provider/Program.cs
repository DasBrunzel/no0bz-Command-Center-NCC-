using System.Text.Json;
using LibreHardwareMonitor.Hardware;

// This helper is deliberately read-only: NCC only asks LHM for sensor values.
// It never writes controls, fan curves, clocks, or firmware settings.
//
// Without arguments it prints one snapshot and exits. With --serve it opens
// the hardware once and prints one snapshot per line read from stdin, so
// low-level sensors (PawnIO modules, SuperIO detection) are not set up again
// for every sample. It exits when stdin closes.
var serve = args.Contains("--serve");
var computer = new Computer {
    IsCpuEnabled = true,
    IsGpuEnabled = true,
    IsMotherboardEnabled = true,
    IsControllerEnabled = true,
    IsMemoryEnabled = true,
    IsStorageEnabled = true,
    // NCC measures network traffic itself.
    IsNetworkEnabled = false,
};

try {
    computer.Open();
    if (serve) {
        while (Console.In.ReadLine() is not null) {
            Console.Out.WriteLine(Snapshot(computer));
            Console.Out.Flush();
        }
    } else {
        Console.Out.WriteLine(Snapshot(computer));
    }
}
catch (Exception error) {
    Console.Error.WriteLine($"ncc-hardware-provider: {error.Message}");
    Environment.ExitCode = 2;
}
finally {
    computer.Close();
}

static string Snapshot(Computer computer) {
    computer.Accept(new UpdateVisitor());
    var sensors = new List<SensorRecord>();
    foreach (var hardware in computer.Hardware) Collect(hardware, sensors);
    // Names without sensors of their own, such as the mainboard model.
    var hardwareList = computer.Hardware
        .Select(item => new HardwareRecord(item.HardwareType.ToString(), item.Name, item.Identifier.ToString()))
        .ToList();
    return JsonSerializer.Serialize(new { schema_version = 1, sensors, hardware = hardwareList });
}

static void Collect(IHardware hardware, List<SensorRecord> output) {
    foreach (var sensor in hardware.Sensors) {
        // Memory timings are static and only inflate every snapshot.
        if (!sensor.Value.HasValue || sensor.SensorType == SensorType.Timing) continue;
        output.Add(new SensorRecord(
            hardware.HardwareType.ToString(), hardware.Name, hardware.Identifier.ToString(),
            sensor.SensorType.ToString(), sensor.Name, Math.Round(sensor.Value.Value, 2), UnitFor(sensor.SensorType)));
    }
    foreach (var child in hardware.SubHardware) Collect(child, output);
}

static string UnitFor(SensorType type) => type switch {
    SensorType.Temperature => "°C",
    SensorType.Fan => "RPM",
    SensorType.Voltage => "V",
    SensorType.Power => "W",
    SensorType.Clock => "MHz",
    SensorType.Load => "%",
    SensorType.Control => "%",
    SensorType.Factor => "%",
    _ => "",
};

sealed record HardwareRecord(string type, string name, string id);

sealed record SensorRecord(string hardware_type, string hardware_name, string hardware_id, string type, string name, double value, string unit);

sealed class UpdateVisitor : IVisitor {
    public void VisitComputer(IComputer computer) => computer.Traverse(this);
    public void VisitHardware(IHardware hardware) {
        hardware.Update();
        foreach (var subHardware in hardware.SubHardware) subHardware.Accept(this);
    }
    public void VisitSensor(ISensor sensor) { }
    public void VisitParameter(IParameter parameter) { }
}
