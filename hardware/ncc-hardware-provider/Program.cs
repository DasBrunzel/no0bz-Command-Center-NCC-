using System.Text.Json;
using LibreHardwareMonitor.Hardware;

// This helper is deliberately read-only: NCC only asks LHM for sensor values.
// It never writes controls, fan curves, clocks, or firmware settings.
var computer = new Computer {
    IsCpuEnabled = true,
    IsGpuEnabled = true,
    IsMotherboardEnabled = true,
    IsControllerEnabled = true,
    IsMemoryEnabled = true,
    IsStorageEnabled = true,
    IsNetworkEnabled = true,
};

try {
    computer.Open();
    computer.Accept(new UpdateVisitor());
    var sensors = new List<SensorRecord>();
    foreach (var hardware in computer.Hardware) Collect(hardware, sensors);
    Console.Out.WriteLine(JsonSerializer.Serialize(new { schema_version = 1, sensors }));
}
catch (Exception error) {
    Console.Error.WriteLine($"ncc-hardware-provider: {error.Message}");
    Environment.ExitCode = 2;
}
finally {
    computer.Close();
}

static void Collect(IHardware hardware, List<SensorRecord> output) {
    foreach (var sensor in hardware.Sensors) {
        if (!sensor.Value.HasValue) continue;
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
    SensorType.Factor => "%",
    _ => "",
};

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
