using DroneGame.Drone;
using TMPro;
using UnityEngine;

namespace DroneGame.UI
{
    // Reads telemetry off DroneController and writes it to TextMeshPro labels.
    // Deliberately dumb (no logic beyond formatting) so it can be reused as-is
    // for a VR world-space HUD by just moving the parent Canvas into World Space
    // and rendering it in front of the cockpit, instead of Screen Space.
    public class DroneHUD : MonoBehaviour
    {
        [SerializeField] private DroneController drone;
        [SerializeField] private TMP_Text altitudeText;
        [SerializeField] private TMP_Text speedText;
        [SerializeField] private TMP_Text batteryText;

        private void Update()
        {
            if (drone == null)
            {
                return;
            }

            altitudeText.text = $"ALT {drone.AltitudeMeters:0.0} m";
            speedText.text = $"SPD {drone.SpeedMetersPerSecond:0.0} m/s";
            batteryText.text = $"BATT {drone.BatteryPercent:0} %";
        }
    }
}
