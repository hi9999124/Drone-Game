using UnityEngine;
using UnityEngine.InputSystem;

namespace DroneGame.Drone
{
    // Wraps the "Flight" action map from DroneControls.inputactions and exposes
    // the current stick values as plain floats. Keeping this separate from
    // DroneController means swapping in a different control source later
    // (a different input map, or a VR hand-tracking rig) only requires a new
    // handler, not changes to the flight physics itself.
    public class DroneInputHandler : MonoBehaviour
    {
        [SerializeField] private InputActionAsset controls;

        private InputAction throttleAction;
        private InputAction pitchAction;
        private InputAction rollAction;
        private InputAction yawAction;
        private InputAction cameraSwitchAction;

        public float Throttle { get; private set; }
        public float Pitch { get; private set; }
        public float Roll { get; private set; }
        public float Yaw { get; private set; }
        public bool CameraSwitchPressedThisFrame { get; private set; }

        private void Awake()
        {
            InputActionMap flightMap = controls.FindActionMap("Flight", throwIfNotFound: true);
            throttleAction = flightMap.FindAction("Throttle");
            pitchAction = flightMap.FindAction("Pitch");
            rollAction = flightMap.FindAction("Roll");
            yawAction = flightMap.FindAction("Yaw");
            cameraSwitchAction = flightMap.FindAction("CameraSwitch");
        }

        private void OnEnable()
        {
            throttleAction.Enable();
            pitchAction.Enable();
            rollAction.Enable();
            yawAction.Enable();
            cameraSwitchAction.Enable();
        }

        private void OnDisable()
        {
            throttleAction.Disable();
            pitchAction.Disable();
            rollAction.Disable();
            yawAction.Disable();
            cameraSwitchAction.Disable();
        }

        private void Update()
        {
            Throttle = throttleAction.ReadValue<float>();
            Pitch = pitchAction.ReadValue<float>();
            Roll = rollAction.ReadValue<float>();
            Yaw = yawAction.ReadValue<float>();
            CameraSwitchPressedThisFrame = cameraSwitchAction.WasPressedThisFrame();
        }
    }
}
