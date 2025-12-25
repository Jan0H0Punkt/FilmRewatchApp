# App Root

## Purpose
The app root contains the bootstrap configuration and top-level structure for the application. It brings together `core`, `shared`, and `features` and configures routing and global providers.

## What Belongs Here
- Application bootstrap configuration and top-level providers
- Top-level routing configuration
- The root application component

## What Does NOT Belong Here
- Business logic (belongs in `features`)
- Reusable component implementations (belongs in `shared`)
- Singleton services (belongs in `core`)

## Key Principles
- **Separation of concerns**: Keep app wiring at the root and move logic into appropriate modules
- **Dependency flow**: Features may depend on `shared` and `core`, but the reverse should be avoided
- **Scalability**: Organize the root so adding new features is straightforward