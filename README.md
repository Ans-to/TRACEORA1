# TRACEORA — See it. Trace it. Create it.

This is a native Android Kotlin/Jetpack Compose MVP foundation for TRACEORA.

## Included working flows
- Compose-based Home / Explore / Create / Lessons / Profile navigation
- Runtime camera permission
- CameraX rear-camera preview
- Camera-overlay tracing workspace
- Pinch zoom, pan and rotation gestures for the reference
- Adjustable overlay opacity
- Grid toggle
- Lock/unlock reference
- Reset transform
- Local artwork persistence using Room
- Gallery-backed artwork metadata
- Device-compatible offline-first structure
- ARCore dependency included for extending the camera workspace to world-anchored tracking

## Important implementation note
The supplied project deliberately keeps the core camera-trace experience usable on devices without ARCore. Full ARCore plane tracking/world anchoring is the next device-specific layer; the fallback camera overlay remains the default reliable path.

## Build
Open the `Traceora` folder in Android Studio, allow Gradle sync, then run on an Android device with a rear camera.

For production release, add:
- a real ARCore Session/plane-anchor renderer
- actual edge/outline processing using RenderScript replacement/OpenCV/ML or GPU image processing
- persisted user settings with DataStore
- complete lesson/achievement tables
- Android Sharesheet capture/export pipeline
- Play Billing product IDs
- accessibility audit
- automated UI/device tests
- crash reporting and analytics
- privacy/terms screens and account deletion


## Phone-only APK build
This project includes a GitHub Actions workflow. Upload the project to a GitHub repository from your phone, open Actions, select **Build TRACEORA APK**, and tap **Run workflow**. GitHub builds the APK in the cloud. Download the `TRACEORA-debug-apk` artifact and install `app-debug.apk` on Android. The core app is designed to work offline after installation.
