# Shared Module

## Purpose
The `shared` folder contains reusable components, directives, pipes, and utilities that are used across multiple features. It serves as the app's component library for generic building blocks.

## What Belongs Here
- **Reusable UI components** used by multiple features (buttons, cards, inputs)
- **Directives** and **pipes** used throughout the app
- **Utilities and helpers** (pure functions, validators) shared across features
- **Common models** and types used in multiple places

## What Does NOT Belong Here
- Feature-specific components tied to a single feature (keep them in the feature)
- Singleton or application-wide services (belong in `core`)

## Key Principles
- **Reusability first**: Only add something if it is (or will be) used by multiple features
- **Generic & configurable**: Keep shared components free of feature-specific logic
- **Documented and tested**: Shared utilities and components should be well-documented and covered by tests