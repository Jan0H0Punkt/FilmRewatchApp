# Core Module

## Purpose
The `core` folder contains singleton services, configuration, and application-level functionality that should be loaded once when the application starts. It provides the foundation and app-wide behaviors used across the app.

## What Belongs Here
- **Singleton services** (e.g., AuthService, ConfigService)
- **HTTP interceptors** for request/response handling
- **Route guards** for app-level authentication/authorization
- **App initialization** services that run before the app starts
- **Global error handlers** and monitoring logic
- **API configuration** and global constants

## What Does NOT Belong Here
- UI components or presentation logic (belong in `shared` or `features`)
- Feature-specific services (belong inside the relevant feature)
- Generic utilities that are reused across features (belong in `shared/utils`)

## Key Principle
- **Import once**: The core module should only be imported at the application bootstrap (e.g., `main.ts` or `app.config.ts`) to keep its services truly singleton and avoid accidental multiple instances.