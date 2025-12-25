# Features Module

## Purpose
The `features` folder contains business feature modules. Each feature should be self-contained with its own pages, components, services, and state management.

## What Belongs Here
- **Feature pages and components** that implement a specific business area
- **Feature-specific services** that encapsulate business logic and data operations
- **Feature state management** (stores, actions, etc.) scoped to the feature
- **Feature models** and types used only by the feature
- **Feature routing** and feature-level guards when needed

## What Does NOT Belong Here
- Components or utilities shared across multiple features (belong in `shared`)
- Application-wide singleton services (belong in `core`)

## Key Principles
- **High cohesion**: Keep everything related to a feature together
- **Low coupling**: Minimize dependencies between features
- **Feature independence**: Make features easy to understand and modify in isolation
- **Lazy-loading ready**: Structure features so they can be lazy-loaded when appropriate