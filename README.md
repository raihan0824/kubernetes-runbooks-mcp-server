# Kubernetes Runbooks MCP Server

A Model Context Protocol (MCP) server that provides access to Kubernetes troubleshooting runbooks from [Container Solutions' Runbooks](https://containersolutions.github.io/runbooks/posts/kubernetes/).

## Features

- **🔍 Search & Discovery**: Find relevant runbooks by keyword or browse all available topics
- **📖 Content Access**: Fetch detailed troubleshooting guides for specific Kubernetes issues
- **🤖 AI Integration**: Designed for seamless integration with AI assistants via MCP
- **⚡ Performance**: Intelligent caching to minimize network requests
- **🛡️ Reliability**: Robust error handling and graceful degradation

## Available Runbooks

The server provides access to comprehensive troubleshooting guides for:

- **Node Issues**: Resource constraints, node availability problems
- **Pod Problems**: CrashLoopBackOff, ImagePullBackOff, pending states
- **Container Errors**: CreateContainerError, sandbox creation failures
- **Network Issues**: Service connectivity, DNS resolution problems
- **Resource Management**: OutOfPods states, resource allocation issues

## Installation

### Using uvx (Recommended)

Install and run directly with uvx:

```bash
uvx kubernetes-runbooks-mcp-server
```

### Using uv

```bash
uv tool install kubernetes-runbooks-mcp-server
kubernetes-runbooks-server
```

### Using pip

```bash
pip install kubernetes-runbooks-mcp-server
kubernetes-runbooks-server
```

## Usage

### With Claude Desktop

Add to your Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "kubernetes-runbooks": {
      "command": "uvx",
      "args": ["kubernetes-runbooks-mcp-server"]
    }
  }
}
```

### Available Tools

- **`list-topics`**: List all available runbook topics
- **`search-runbooks`**: Search runbooks by keyword
- **`fetch-runbook`**: Get specific runbook content by topic slug

### Available Resources

Access runbooks directly via URI:
- `runbook://kubernetes/create-container-error`
- `runbook://kubernetes/crashloopbackoff`
- `runbook://kubernetes/dns-failures`

### Available Prompts

- **`troubleshoot-k8s`**: Interactive troubleshooting guidance
- **`runbook-summary`**: Summarize key points from runbooks

## Example Usage

```bash
# List all available topics
{"name": "list-topics", "arguments": {}}

# Search for pod-related issues
{"name": "search-runbooks", "arguments": {"query": "pod"}}

# Fetch specific runbook
{"name": "fetch-runbook", "arguments": {"topic": "crashloopbackoff"}}
```

## Development

### Setup

```bash
git clone <repository-url>
cd kubernetes-runbooks-mcp-server
uv sync --dev
```

### Running

```bash
uv run kubernetes-runbooks-server
```

### Testing

```bash
uv run pytest
```

## Architecture

- **RunbookScraper**: Handles web scraping from the runbooks website
- **Caching System**: In-memory cache for runbook metadata and content
- **MCP Server**: Implements the Model Context Protocol with resources, tools, and prompts

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- [Container Solutions](https://containersolutions.github.io/) for maintaining excellent Kubernetes runbooks
- [Model Context Protocol](https://modelcontextprotocol.io/) for the MCP specification 