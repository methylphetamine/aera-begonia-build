# AGENTS

This file documents the agents used in this repository for building and testing.

## Overview

Agents in this repository are specialized tools that help automate complex workflows, particularly for building recovery images and testing. They are typically implemented as GitHub Actions or local scripts that handle specific tasks in the build process.

## Common Patterns

- **Build Agents**: Tools that compile source code, run tests, and produce artifacts
- **Test Agents**: Tools that validate the build output and run comprehensive testing
- **Utility Agents**: Tools that perform maintenance tasks like disk cleanup, dependency management, and configuration

## Available Agents

### Build Agents

- **Compile Agent**: Handles the compilation of the AOSP source code using Soong and Make
- **Prune Agent**: Identifies and removes test-only source trees to reduce build complexity
- **Sync Agent**: Manages synchronization of source code from external repositories

### Test Agents

- **Unit Test Agent**: Runs unit tests for individual components
- **Integration Test Agent**: Performs integration tests across multiple components
- **End-to-End Test Agent**: Validates the complete recovery image functionality

### Utility Agents

- **Memory Management Agent**: Handles memory pressure and swap configuration during builds
- **Disk Cleanup Agent**: Performs disk space management before and during build processes
- **Configuration Agent**: Sets up build environment variables and dependencies

## Agent Configuration

Each agent can be configured through environment variables or GitHub Actions inputs:

```yaml
env:
  AGENT_TYPE: "build"
  AGENT_MODE: "compile"
  MAX_JOBS: "4"
```

## Agent Execution

Agents are typically executed in a specific order:

1. **Setup Phase**: Initial configuration and environment preparation
2. **Sync Phase**: Retrieve and prepare source code
3. **Build Phase**: Compile source code and produce artifacts
4. **Test Phase**: Validate build output
5. **Deploy Phase**: Distribute built artifacts

## Agent Monitoring

Agent execution is monitored through:

- GitHub Actions logs and status checks
- Custom monitoring scripts for resource usage
- Alerting for failures or timeouts

## Agent Maintenance

Regular maintenance tasks include:

- Updating agent scripts and dependencies
- Monitoring agent performance
- Reviewing agent logs for errors
- Optimizing agent configurations

## See Also

- [GitHub Actions Workflow Documentation](/.github/workflows/README.md)
- [Build Process Documentation](/BUILD.md)
- [Test Documentation](/TEST.md)