using System;
using DroneGame.Drone;
using UnityEngine;

namespace DroneGame.Camera
{
    public enum CameraViewMode
    {
        FirstPerson,
        ThirdPerson,
        TopDown
    }

    // Holds one Camera per view mode as children and enables only the active one,
    // rather than repositioning a single camera. That keeps each mode independently
    // tunable in the Inspector, and keeps the FirstPerson slot VR-ready: an XR Origin
    // rig can be parented there later (Phase 5) without touching this script or the
    // flight/aim code that depends on it.
    public class CameraRig : MonoBehaviour
    {
        [SerializeField] private UnityEngine.Camera firstPersonCamera;
        [SerializeField] private UnityEngine.Camera thirdPersonCamera;
        [SerializeField] private UnityEngine.Camera topDownCamera;
        [SerializeField] private CameraViewMode startingMode = CameraViewMode.ThirdPerson;
        [SerializeField] private DroneInputHandler input;

        public CameraViewMode CurrentMode { get; private set; }

        private void Start()
        {
            SetMode(startingMode);
        }

        private void Update()
        {
            if (input != null && input.CameraSwitchPressedThisFrame)
            {
                CycleMode();
            }
        }

        public void CycleMode()
        {
            int modeCount = Enum.GetValues(typeof(CameraViewMode)).Length;
            SetMode((CameraViewMode)(((int)CurrentMode + 1) % modeCount));
        }

        public void SetMode(CameraViewMode mode)
        {
            CurrentMode = mode;
            firstPersonCamera.gameObject.SetActive(mode == CameraViewMode.FirstPerson);
            thirdPersonCamera.gameObject.SetActive(mode == CameraViewMode.ThirdPerson);
            topDownCamera.gameObject.SetActive(mode == CameraViewMode.TopDown);
        }
    }
}
