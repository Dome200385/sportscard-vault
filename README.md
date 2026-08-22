# Mobile V0.1
Flutter source for the first Android shell.

Because Flutter is not installed in the build environment used to create this pack, this source was structurally prepared but not compiled here. On a machine with Flutter:
```bash
flutter create . --platforms=android
flutter pub get
flutter run
```
The default API URL is `http://10.0.2.2:8000` for an Android emulator. For a physical phone, replace it with the LAN or deployed Render URL.
