# aOS - Android-Like Operating System

A complete, multi-language implementation of an Android-like operating system with Google OAuth 2.0 authentication, native app framework, permission system, and more.

## Architecture Overview

```
aOS
├── Kernel (C) - Low-level OS operations
├── System Framework (Java/Kotlin) - Core Android-like framework
├── UI Framework (TypeScript/React) - Display & interaction layer
├── Backend Services (Python) - Google Auth & system services
├── App Manager (Java) - Package management & app lifecycle
└── Native Libraries (C++) - Performance-critical operations
```

## Core Features

✅ **Google OAuth 2.0 Integration** - Complete authentication system
✅ **Activity & Fragment System** - Android-like UI components
✅ **Permission Management** - Fine-grained app permissions
✅ **Package Manager** - APK-like app installation & management
✅ **Service Framework** - Background services & IPC
✅ **Content Providers** - Data sharing between apps
✅ **Broadcast Receivers** - Event system
✅ **Virtual File System** - Sandboxed file access
✅ **Multi-user Support** - User profiles & device owner
✅ **App Lifecycle Management** - State preservation & restoration

## Quick Start

### Prerequisites
- Java 11+
- Python 3.9+
- Node.js 16+
- GCC/Clang (C compiler)
- Kotlin 1.5+

### Installation

```bash
git clone https://github.com/aapps2025a-hue/aOS.git
cd aOS

# Setup backend (Python)
cd backend
pip install -r requirements.txt
python app.py

# Setup frontend (TypeScript/React)
cd ../frontend
npm install
npm start

# Compile system framework (Java)
cd ../kernel/system-framework
./gradlew build

# Build native components (C)
cd ../native
make
```

## Project Structure

- **kernel/** - OS kernel and low-level operations
- **framework/** - Android-like framework components
- **ui/** - React-based UI system
- **backend/** - Python services & Google OAuth
- **apps/** - Built-in system apps
- **native/** - C/C++ libraries
- **docs/** - Complete documentation

## Google OAuth 2.0 Setup

1. Create OAuth credentials at [Google Cloud Console](https://console.cloud.google.com)
2. Configure redirect URI: `http://localhost:5000/auth/google/callback`
3. Add credentials to `backend/.env`:
   ```
   GOOGLE_CLIENT_ID=your_client_id
   GOOGLE_CLIENT_SECRET=your_client_secret
   ```

## Development

### Build System
- **Kernel & Framework**: Gradle
- **UI**: Webpack
- **Backend**: Python setuptools
- **Native**: Make/CMake

### Testing
```bash
./scripts/run-tests.sh
```

### Documentation
See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture.

## License

MIT License - See LICENSE file

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md)
