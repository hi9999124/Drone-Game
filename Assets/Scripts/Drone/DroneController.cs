using UnityEngine;

namespace DroneGame.Drone
{
    // Physics-based drone flight. All movement goes through Rigidbody forces/torques
    // (never by setting transform.position directly) so the drone collides and
    // reacts to impacts correctly, and so this same component can later be driven
    // by AI input (Phase 3) just by feeding a DroneInputHandler-shaped source.
    [RequireComponent(typeof(Rigidbody))]
    [RequireComponent(typeof(DroneInputHandler))]
    public class DroneController : MonoBehaviour
    {
        [Header("Thrust")]
        [SerializeField] private float maxExtraThrust = 20f;
        [SerializeField] private float hoverThrust = 9.81f; // roughly cancels gravity so Throttle == 0 holds altitude

        [Header("Rotation")]
        [SerializeField] private float pitchTorque = 6f;
        [SerializeField] private float rollTorque = 6f;
        [SerializeField] private float yawTorque = 4f;
        [SerializeField] private float angularDamping = 2f;

        [Header("Battery")]
        [SerializeField] private float batteryDrainPercentPerSecond = 1f;

        private Rigidbody rb;
        private DroneInputHandler input;
        private float batteryPercent = 100f;

        public float AltitudeMeters => transform.position.y;
        public float SpeedMetersPerSecond => rb.velocity.magnitude;
        public float BatteryPercent => batteryPercent;

        private void Awake()
        {
            rb = GetComponent<Rigidbody>();
            input = GetComponent<DroneInputHandler>();
        }

        // Physics forces belong in FixedUpdate, which runs on Unity's fixed
        // timestep (default 50Hz) independent of frame rate. Update() runs once
        // per rendered frame, so using it for forces would make the drone behave
        // differently at different frame rates.
        private void FixedUpdate()
        {
            ApplyThrust();
            ApplyRotation();
            DrainBattery();
        }

        private void ApplyThrust()
        {
            float thrust = hoverThrust + input.Throttle * maxExtraThrust;
            rb.AddForce(transform.up * thrust, ForceMode.Force);
        }

        private void ApplyRotation()
        {
            Vector3 torque =
                transform.right * (input.Pitch * pitchTorque) +
                transform.forward * (input.Roll * rollTorque) +
                transform.up * (input.Yaw * yawTorque);

            rb.AddTorque(torque, ForceMode.Force);

            // Unity's built-in Angular Drag is linear and makes rotation feel
            // sluggish to start and never quite settle; blending angular velocity
            // toward zero each step gives a snappier, more controllable feel.
            rb.angularVelocity = Vector3.Lerp(rb.angularVelocity, Vector3.zero, angularDamping * Time.fixedDeltaTime);
        }

        private void DrainBattery()
        {
            batteryPercent = Mathf.Max(0f, batteryPercent - batteryDrainPercentPerSecond * Time.fixedDeltaTime);
        }
    }
}
