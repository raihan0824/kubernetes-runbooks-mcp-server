#!/usr/bin/env python3
"""
Kubernetes Runbooks MCP Server

A Model Context Protocol server that fetches Kubernetes troubleshooting runbooks
from https://containersolutions.github.io/runbooks/posts/kubernetes/

Usage:
    python kubernetes_runbooks_server.py

Features:
- Fetch individual runbooks by topic
- Search through available runbooks
- List all available topics
- Troubleshooting prompts
- Resource-based access to runbook content
"""

import asyncio
import re
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
from pydantic import AnyUrl
import mcp.server.stdio

# Cache for runbook content
runbooks_cache: Dict[str, Dict] = {}
BASE_URL = "https://containersolutions.github.io/runbooks/posts/kubernetes/"

server = Server("kubernetes-runbooks-server")

class RunbookScraper:
    """Scraper for Kubernetes runbooks from containersolutions.github.io"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; MCP-KubernetesRunbooks/1.0)"
            }
        )
    
    async def fetch_runbook_index(self) -> List[Dict]:
        """Fetch the main index page and extract runbook links"""
        try:
            response = await self.client.get(BASE_URL)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            runbooks = []
            
            # Look for runbook links in the main content area
            # The site uses a specific structure with links to individual runbooks
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                if href and '/posts/kubernetes/' in href and href != '/posts/kubernetes/':
                    title = link.get_text(strip=True)
                    # Filter out navigation links and empty titles
                    if (title and 
                        not title.startswith('Prev') and 
                        not title.startswith('Next') and
                        not title.startswith('1') and  # Page numbers
                        not title.startswith('2') and
                        title != '…' and
                        len(title) > 3):  # Avoid very short titles
                        
                        # Create proper absolute URL
                        full_url = urljoin("https://containersolutions.github.io", href)
                        slug = href.split('/')[-2] if href.endswith('/') else href.split('/')[-1]
                        
                        runbooks.append({
                            'title': title,
                            'url': full_url,
                            'slug': slug
                        })
            
            # Remove duplicates based on slug
            seen_slugs = set()
            unique_runbooks = []
            for runbook in runbooks:
                if runbook['slug'] not in seen_slugs:
                    seen_slugs.add(runbook['slug'])
                    unique_runbooks.append(runbook)
            
            return unique_runbooks
            
        except Exception as e:
            print(f"Error fetching runbook index: {e}")
            return []
    
    async def fetch_runbook_content(self, url: str) -> Optional[Dict]:
        """Fetch content from a specific runbook page"""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract title - try multiple selectors
            title = ""
            title_selectors = ['h1', '.post-title', '.entry-title', 'title']
            for selector in title_selectors:
                title_elem = soup.find(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    break
            
            # Extract main content - try multiple content areas
            content = ""
            content_selectors = [
                'main',
                'article', 
                '.post-content',
                '.entry-content',
                '.content',
                '.post',
                'body'
            ]
            
            for selector in content_selectors:
                main_content = soup.find(selector)
                if main_content:
                    # Remove navigation, header, footer elements
                    for unwanted in main_content.find_all(['nav', 'header', 'footer', '.nav', '.navigation']):
                        unwanted.decompose()
                    
                    # Get text content while preserving structure
                    content = main_content.get_text(separator='\n', strip=True)
                    
                    # Clean up excessive whitespace
                    content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
                    content = re.sub(r'[ \t]+', ' ', content)
                    
                    # If we got substantial content, break
                    if len(content) > 100:
                        break
            
            # If still no content, try to get all text from body
            if len(content) < 100:
                body = soup.find('body')
                if body:
                    # Remove script and style elements
                    for script in body(["script", "style"]):
                        script.decompose()
                    content = body.get_text(separator='\n', strip=True)
                    content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
            
            return {
                'title': title or "Untitled Runbook",
                'content': content,
                'url': url,
                'description': content[:200] + "..." if len(content) > 200 else content
            }
            
        except Exception as e:
            print(f"Error fetching runbook content from {url}: {e}")
            return None
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

# Global scraper instance
scraper = RunbookScraper()

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """
    List available Kubernetes runbook resources.
    Each runbook is exposed as a resource with a custom runbook:// URI scheme.
    """
    if not runbooks_cache:
        # Fetch runbooks if cache is empty
        runbooks = await scraper.fetch_runbook_index()
        for runbook in runbooks:
            runbooks_cache[runbook['slug']] = runbook
    
    resources = []
    for slug, runbook in runbooks_cache.items():
        resources.append(
            types.Resource(
                uri=AnyUrl(f"runbook://kubernetes/{slug}"),
                name=f"Kubernetes Runbook: {runbook['title']}",
                description=f"Kubernetes troubleshooting guide: {runbook['title']}",
                mimeType="text/plain",
            )
        )
    
    return resources

@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    """
    Read a specific runbook's content by its URI.
    The runbook slug is extracted from the URI path.
    """
    if uri.scheme != "runbook":
        raise ValueError(f"Unsupported URI scheme: {uri.scheme}")
    
    # For runbook://kubernetes/slug, the host is 'kubernetes' and path is '/slug'
    if uri.host != "kubernetes":
        raise ValueError(f"Invalid runbook URI - expected kubernetes host: {uri}")
    
    # Extract slug from path (remove leading slash)
    slug = uri.path.lstrip('/')
    if not slug:
        raise ValueError(f"Invalid runbook URI - no slug provided: {uri}")
    
    # Check if we have the runbook in cache
    if slug not in runbooks_cache:
        # Try to fetch from index first
        runbooks = await scraper.fetch_runbook_index()
        for runbook in runbooks:
            runbooks_cache[runbook['slug']] = runbook
    
    if slug not in runbooks_cache:
        raise ValueError(f"Runbook not found: {slug}")
    
    runbook = runbooks_cache[slug]
    
    # Fetch full content if not already cached
    if 'content' not in runbook:
        content_data = await scraper.fetch_runbook_content(runbook['url'])
        if content_data:
            runbook.update(content_data)
        else:
            raise ValueError(f"Failed to fetch runbook content: {slug}")
    
    return f"# {runbook['title']}\n\n{runbook['content']}\n\nSource: {runbook['url']}"

@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    """
    List available prompts for Kubernetes troubleshooting.
    """
    return [
        types.Prompt(
            name="troubleshoot-k8s",
            description="Get troubleshooting guidance for Kubernetes issues",
            arguments=[
                types.PromptArgument(
                    name="symptoms",
                    description="Describe the symptoms or error messages you're seeing",
                    required=True,
                ),
                types.PromptArgument(
                    name="context",
                    description="Additional context about your Kubernetes setup",
                    required=False,
                )
            ],
        ),
        types.Prompt(
            name="runbook-summary",
            description="Summarize key points from Kubernetes runbooks",
            arguments=[
                types.PromptArgument(
                    name="topics",
                    description="Comma-separated list of topics to summarize",
                    required=False,
                )
            ],
        )
    ]

@server.get_prompt()
async def handle_get_prompt(
    name: str, arguments: dict[str, str] | None
) -> types.GetPromptResult:
    """
    Generate prompts for Kubernetes troubleshooting.
    """
    if name == "troubleshoot-k8s":
        symptoms = (arguments or {}).get("symptoms", "")
        context = (arguments or {}).get("context", "")
        
        if not symptoms:
            raise ValueError("Symptoms are required for troubleshooting")
        
        context_text = f"\nAdditional context: {context}" if context else ""
        
        return types.GetPromptResult(
            description="Kubernetes troubleshooting guidance",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=f"I'm experiencing the following Kubernetes issue:\n\nSymptoms: {symptoms}{context_text}\n\nPlease help me troubleshoot this issue using the available Kubernetes runbooks. Provide step-by-step guidance and relevant commands.",
                    ),
                )
            ],
        )
    
    elif name == "runbook-summary":
        topics = (arguments or {}).get("topics", "")
        
        return types.GetPromptResult(
            description="Summarize Kubernetes runbooks",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=f"Please provide a summary of the key troubleshooting steps and solutions from the Kubernetes runbooks{f' for topics: {topics}' if topics else ''}. Focus on the most common issues and their solutions.",
                    ),
                )
            ],
        )
    
    else:
        raise ValueError(f"Unknown prompt: {name}")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    List available tools for interacting with Kubernetes runbooks.
    """
    return [
        types.Tool(
            name="fetch-runbook",
            description="Fetch a specific Kubernetes runbook by topic",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "The runbook topic/slug to fetch"
                    }
                },
                "required": ["topic"],
            },
        ),
        types.Tool(
            name="search-runbooks",
            description="Search through Kubernetes runbooks by keyword",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for finding relevant runbooks"
                    }
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="list-topics",
            description="List all available Kubernetes runbook topics",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Handle tool execution requests for Kubernetes runbooks.
    """
    if name == "fetch-runbook":
        if not arguments or "topic" not in arguments:
            raise ValueError("Topic is required")
        
        topic = arguments["topic"]
        
        try:
            # Try to read the resource
            uri = AnyUrl(f"runbook://kubernetes/{topic}")
            content = await handle_read_resource(uri)
            
            return [
                types.TextContent(
                    type="text",
                    text=content,
                )
            ]
        except Exception as e:
            return [
                types.TextContent(
                    type="text",
                    text=f"Error fetching runbook '{topic}': {str(e)}",
                )
            ]
    
    elif name == "search-runbooks":
        if not arguments or "query" not in arguments:
            raise ValueError("Query is required")
        
        query = arguments["query"].lower()
        
        # Ensure runbooks are loaded
        if not runbooks_cache:
            runbooks = await scraper.fetch_runbook_index()
            for runbook in runbooks:
                runbooks_cache[runbook['slug']] = runbook
        
        # Search through runbook titles
        matching_runbooks = []
        for slug, runbook in runbooks_cache.items():
            if query in runbook['title'].lower() or query in slug.lower():
                matching_runbooks.append(f"- **{runbook['title']}** (slug: {slug})")
        
        if matching_runbooks:
            result = f"Found {len(matching_runbooks)} runbooks matching '{query}':\n\n" + "\n".join(matching_runbooks)
        else:
            result = f"No runbooks found matching '{query}'"
        
        return [
            types.TextContent(
                type="text",
                text=result,
            )
        ]
    
    elif name == "list-topics":
        # Ensure runbooks are loaded
        if not runbooks_cache:
            runbooks = await scraper.fetch_runbook_index()
            for runbook in runbooks:
                runbooks_cache[runbook['slug']] = runbook
        
        if runbooks_cache:
            topics = []
            for slug, runbook in runbooks_cache.items():
                topics.append(f"- **{runbook['title']}** (slug: {slug})")
            
            result = f"Available Kubernetes runbook topics ({len(topics)} total):\n\n" + "\n".join(topics)
        else:
            result = "No runbook topics found"
        
        return [
            types.TextContent(
                type="text",
                text=result,
            )
        ]
    
    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    """Main entry point for the Kubernetes runbooks MCP server."""
    try:
        # Run the server using stdin/stdout streams
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="kubernetes-runbooks-server",
                    server_version="0.1.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
    finally:
        # Clean up the scraper
        await scraper.close()

def cli():
    """Synchronous entry point for the CLI script."""
    asyncio.run(main())

if __name__ == "__main__":
    cli() 