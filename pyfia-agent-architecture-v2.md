# pyFIA Agent: Public Forest Inventory Query Tool
## Architecture & Implementation Guide v2

**Modern Full-Stack Architecture with Next.js, FastAPI, and pyFIA**

---

## Overview

A public-facing web application that allows users to:
1. Ask natural language questions about forest inventory
2. Generate automated reports on forest conditions
3. Create custom data downloads from the FIA database
4. Visualize forest data with interactive charts and maps

**Tech Stack:**
- **Frontend**: Next.js 15 + Vercel AI SDK + shadcn/ui + Tailwind CSS
- **Backend**: FastAPI + LangChain + Claude
- **Data**: pyFIA (DuckDB/Polars) for validated FIA statistics
- **Deployment**: Self-hosted or cloud (Vercel + Railway/Fly.io)

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USERS                                          │
│                    (Researchers, Land Managers, Public)                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     FRONTEND (Next.js 15 App Router)                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  shadcn/ui + Tailwind CSS + Vercel AI SDK                           │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐           │   │
│  │  │   Chat    │ │  Reports  │ │   Data    │ │   Map     │           │   │
│  │  │   Page    │ │   Page    │ │  Explorer │ │  Viewer   │           │   │
│  │  └───────────┘ └───────────┘ └───────────┘ └───────────┘           │   │
│  │                                                                     │   │
│  │  • useChat() hook for streaming                                    │   │
│  │  • Server Components for SEO                                        │   │
│  │  • Client Components for interactivity                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                          REST API + Data Stream Protocol
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        BACKEND (FastAPI + Python)                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                   LangChain Agent + Claude Sonnet                    │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │   │
│  │  │  Area   │ │ Volume  │ │ Biomass │ │  TPA    │ │Mortality│       │   │
│  │  │  Tool   │ │  Tool   │ │  Tool   │ │  Tool   │ │  Tool   │       │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘       │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐                               │   │
│  │  │ Growth  │ │Download │ │ Compare │                               │   │
│  │  │  Tool   │ │  Tool   │ │  Tool   │                               │   │
│  │  └─────────┘ └─────────┘ └─────────┘                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                           pyFIA Library                              │   │
│  │    download() → FIA() → area() / volume() / biomass() / tpa()       │   │
│  │         DuckDB backend  •  Polars DataFrames  •  EVALIDator match   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA LAYER                                        │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                 │
│   │ DuckDB Files │    │  FIA DataMart│    │    Redis     │                 │
│   │ (Per-State)  │    │ (Downloads)  │    │   (Cache)    │                 │
│   └──────────────┘    └──────────────┘    └──────────────┘                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Frontend Architecture (Next.js 15)

### Project Structure

```
frontend/
├── app/
│   ├── layout.tsx              # Root layout with providers
│   ├── page.tsx                # Landing page
│   ├── (chat)/
│   │   └── page.tsx            # Main chat interface
│   ├── explore/
│   │   └── page.tsx            # Data explorer
│   ├── reports/
│   │   └── page.tsx            # Report generation
│   ├── downloads/
│   │   └── page.tsx            # Download center
│   └── api/
│       └── chat/
│           └── route.ts        # Proxy to FastAPI backend
├── components/
│   ├── ui/                     # shadcn/ui components
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── input.tsx
│   │   └── ...
│   ├── chat/
│   │   ├── chat-interface.tsx  # Main chat component
│   │   ├── message.tsx         # Message display
│   │   ├── message-list.tsx    # Scrollable message list
│   │   ├── chat-input.tsx      # Input with suggestions
│   │   └── tool-result.tsx     # Display tool outputs
│   ├── data/
│   │   ├── state-selector.tsx  # Multi-state picker
│   │   ├── metric-card.tsx     # Display FIA metrics
│   │   └── data-table.tsx      # Results table
│   ├── viz/
│   │   ├── area-chart.tsx      # Forest area charts
│   │   ├── species-pie.tsx     # Species composition
│   │   └── state-map.tsx       # Interactive US map
│   └── layout/
│       ├── header.tsx
│       ├── sidebar.tsx
│       └── footer.tsx
├── lib/
│   ├── api.ts                  # API client utilities
│   ├── utils.ts                # Helper functions
│   └── constants.ts            # State codes, metrics, etc.
├── hooks/
│   └── use-fia-query.ts        # Custom hooks for FIA data
├── styles/
│   └── globals.css             # Tailwind + custom CSS
├── public/
│   └── ...                     # Static assets
├── next.config.js
├── tailwind.config.js
├── tsconfig.json
└── package.json
```

### Core Chat Interface

```tsx
// app/(chat)/page.tsx
'use client';

import { useChat } from '@ai-sdk/react';
import { ChatInterface } from '@/components/chat/chat-interface';

export default function ChatPage() {
  const {
    messages,
    input,
    handleInputChange,
    handleSubmit,
    isLoading,
    stop,
    error,
    reload,
  } = useChat({
    api: '/api/chat',
    initialMessages: [
      {
        id: 'welcome',
        role: 'assistant',
        content: `Welcome to the Forest Inventory Explorer! 🌲

I can help you understand forest resources across the United States using data from the USDA Forest Service Forest Inventory and Analysis (FIA) program.

**Try asking:**
- "How much forest land is in North Carolina?"
- "Compare timber volume in Georgia, South Carolina, and Florida"
- "What are the top tree species by biomass in Oregon?"
- "Show me forest carbon stocks in California"

All statistics are validated against official USFS estimates.`,
      },
    ],
  });

  const suggestions = [
    "How much forest is in Georgia?",
    "Compare forest area in NC, SC, and VA",
    "What's the timber volume in Oregon?",
    "Show carbon stocks in California",
  ];

  return (
    <ChatInterface
      messages={messages}
      input={input}
      onInputChange={handleInputChange}
      onSubmit={handleSubmit}
      isLoading={isLoading}
      onStop={stop}
      error={error}
      onReload={reload}
      suggestions={suggestions}
    />
  );
}
```

### Chat Component with shadcn/ui

```tsx
// components/chat/chat-interface.tsx
'use client';

import { useRef, useEffect } from 'react';
import { Message } from '@ai-sdk/react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Card } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { 
  Send, 
  StopCircle, 
  RefreshCw, 
  Trees, 
  User,
  Sparkles 
} from 'lucide-react';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import { ToolResult } from './tool-result';

interface ChatInterfaceProps {
  messages: Message[];
  input: string;
  onInputChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  onSubmit: (e: React.FormEvent) => void;
  isLoading: boolean;
  onStop: () => void;
  error?: Error;
  onReload: () => void;
  suggestions?: string[];
}

export function ChatInterface({
  messages,
  input,
  onInputChange,
  onSubmit,
  isLoading,
  onStop,
  error,
  onReload,
  suggestions = [],
}: ChatInterfaceProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // Focus input on load
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSubmit(e as any);
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    const event = {
      target: { value: suggestion },
    } as React.ChangeEvent<HTMLTextAreaElement>;
    onInputChange(event);
    // Auto-submit after brief delay
    setTimeout(() => {
      const form = document.querySelector('form');
      form?.requestSubmit();
    }, 100);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] max-w-4xl mx-auto">
      {/* Messages Area */}
      <ScrollArea ref={scrollRef} className="flex-1 p-4">
        <div className="space-y-6">
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          
          {isLoading && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Sparkles className="h-4 w-4 animate-pulse" />
              <span className="text-sm">Querying FIA data...</span>
            </div>
          )}
          
          {error && (
            <Card className="p-4 border-destructive bg-destructive/10">
              <p className="text-sm text-destructive">
                Error: {error.message}
              </p>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={onReload}
                className="mt-2"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Retry
              </Button>
            </Card>
          )}
        </div>
      </ScrollArea>

      {/* Suggestions (show when no messages or few messages) */}
      {messages.length <= 1 && suggestions.length > 0 && (
        <div className="px-4 pb-2">
          <p className="text-sm text-muted-foreground mb-2">
            Try one of these:
          </p>
          <div className="flex flex-wrap gap-2">
            {suggestions.map((suggestion, i) => (
              <Button
                key={i}
                variant="outline"
                size="sm"
                onClick={() => handleSuggestionClick(suggestion)}
                className="text-xs"
              >
                {suggestion}
              </Button>
            ))}
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className="border-t bg-background p-4">
        <form onSubmit={onSubmit} className="flex gap-2">
          <Textarea
            ref={inputRef}
            value={input}
            onChange={onInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask about forest inventory..."
            className="min-h-[60px] max-h-[200px] resize-none"
            disabled={isLoading}
          />
          {isLoading ? (
            <Button type="button" onClick={onStop} variant="destructive">
              <StopCircle className="h-4 w-4" />
            </Button>
          ) : (
            <Button type="submit" disabled={!input.trim()}>
              <Send className="h-4 w-4" />
            </Button>
          )}
        </form>
        <p className="text-xs text-muted-foreground mt-2 text-center">
          Data from USDA Forest Service FIA • Validated with pyFIA
        </p>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user';

  return (
    <div className={cn('flex gap-3', isUser && 'flex-row-reverse')}>
      <Avatar className="h-8 w-8">
        <AvatarFallback className={cn(
          isUser ? 'bg-primary text-primary-foreground' : 'bg-green-600 text-white'
        )}>
          {isUser ? <User className="h-4 w-4" /> : <Trees className="h-4 w-4" />}
        </AvatarFallback>
      </Avatar>
      
      <Card className={cn(
        'max-w-[80%] p-4',
        isUser ? 'bg-primary text-primary-foreground' : 'bg-muted'
      )}>
        {message.toolInvocations ? (
          <div className="space-y-4">
            {message.toolInvocations.map((tool, i) => (
              <ToolResult key={i} tool={tool} />
            ))}
            {message.content && (
              <div className="prose prose-sm dark:prose-invert">
                <ReactMarkdown>{message.content}</ReactMarkdown>
              </div>
            )}
          </div>
        ) : (
          <div className="prose prose-sm dark:prose-invert">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}
      </Card>
    </div>
  );
}
```

### Tool Result Display Component

```tsx
// components/chat/tool-result.tsx
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  TreeDeciduous, 
  Mountain, 
  Leaf, 
  TrendingUp,
  Download,
  BarChart3
} from 'lucide-react';

interface ToolResultProps {
  tool: {
    toolName: string;
    args: Record<string, any>;
    state: 'partial-call' | 'call' | 'result';
    result?: any;
  };
}

const toolIcons: Record<string, any> = {
  query_forest_area: Mountain,
  query_timber_volume: TreeDeciduous,
  query_biomass_carbon: Leaf,
  query_trees_per_acre: BarChart3,
  query_mortality: TrendingUp,
  query_growth: TrendingUp,
  prepare_data_download: Download,
  compare_states: BarChart3,
};

const toolLabels: Record<string, string> = {
  query_forest_area: 'Forest Area',
  query_timber_volume: 'Timber Volume',
  query_biomass_carbon: 'Biomass & Carbon',
  query_trees_per_acre: 'Trees Per Acre',
  query_mortality: 'Mortality',
  query_growth: 'Growth',
  prepare_data_download: 'Data Download',
  compare_states: 'State Comparison',
};

export function ToolResult({ tool }: ToolResultProps) {
  const Icon = toolIcons[tool.toolName] || BarChart3;
  const label = toolLabels[tool.toolName] || tool.toolName;

  if (tool.state === 'call' || tool.state === 'partial-call') {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Icon className="h-4 w-4 animate-pulse" />
        <span className="text-sm">Querying {label}...</span>
        {tool.args.states && (
          <Badge variant="outline" className="text-xs">
            {Array.isArray(tool.args.states) 
              ? tool.args.states.join(', ') 
              : tool.args.states}
          </Badge>
        )}
      </div>
    );
  }

  return (
    <Card className="p-3 bg-background/50">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="h-4 w-4 text-green-600" />
        <span className="text-sm font-medium">{label}</span>
        <Badge variant="secondary" className="text-xs">
          {Array.isArray(tool.args.states) 
            ? tool.args.states.join(', ') 
            : tool.args.states || 'Query'}
        </Badge>
      </div>
      {/* Result is included in the main message content */}
    </Card>
  );
}
```

### API Route (Proxy to FastAPI)

```typescript
// app/api/chat/route.ts
import { createDataStreamResponse, streamText } from 'ai';

export const maxDuration = 60; // Allow longer for FIA queries

export async function POST(req: Request) {
  const { messages } = await req.json();

  // Proxy to FastAPI backend
  const response = await fetch(`${process.env.BACKEND_URL}/api/v1/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ messages }),
  });

  if (!response.ok) {
    return new Response(
      JSON.stringify({ error: 'Backend error' }),
      { status: response.status }
    );
  }

  // Stream the response back to the client
  return new Response(response.body, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  });
}
```

### Alternative: Direct Claude Integration (No Python Backend)

If you want to skip the Python backend for the chat interface and call Claude directly from Next.js:

```typescript
// app/api/chat/route.ts
import { anthropic } from '@ai-sdk/anthropic';
import { streamText, tool } from 'ai';
import { z } from 'zod';

export const maxDuration = 60;

export async function POST(req: Request) {
  const { messages } = await req.json();

  const result = streamText({
    model: anthropic('claude-sonnet-4-5-20250929'),
    system: `You are a forest inventory analyst with access to the USDA Forest Service 
    Forest Inventory and Analysis (FIA) database through pyFIA tools.
    
    When users ask about forest data, use the appropriate tools to query the database.
    Always cite "USDA Forest Service FIA" as the data source and include standard errors 
    when reporting estimates.`,
    messages,
    tools: {
      queryForestArea: tool({
        description: 'Query forest land area from FIA database',
        parameters: z.object({
          states: z.array(z.string()).describe('State codes like NC, GA, OR'),
          landType: z.enum(['forest', 'timber', 'reserved']).default('forest'),
        }),
        execute: async ({ states, landType }) => {
          // Call your Python API for the actual pyFIA query
          const res = await fetch(`${process.env.PYFIA_API_URL}/query/area`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ states, land_type: landType }),
          });
          return res.json();
        },
      }),
      queryTimberVolume: tool({
        description: 'Query timber volume estimates',
        parameters: z.object({
          states: z.array(z.string()),
          bySpecies: z.boolean().default(false),
        }),
        execute: async ({ states, bySpecies }) => {
          const res = await fetch(`${process.env.PYFIA_API_URL}/query/volume`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ states, by_species: bySpecies }),
          });
          return res.json();
        },
      }),
      queryBiomassCarbon: tool({
        description: 'Query biomass and carbon stocks',
        parameters: z.object({
          states: z.array(z.string()),
          landType: z.enum(['forest', 'timber']).default('forest'),
        }),
        execute: async ({ states, landType }) => {
          const res = await fetch(`${process.env.PYFIA_API_URL}/query/biomass`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ states, land_type: landType }),
          });
          return res.json();
        },
      }),
      compareStates: tool({
        description: 'Compare forest metrics across multiple states',
        parameters: z.object({
          states: z.array(z.string()),
          metric: z.enum(['area', 'volume', 'biomass', 'tpa', 'mortality', 'growth']),
        }),
        execute: async ({ states, metric }) => {
          const res = await fetch(`${process.env.PYFIA_API_URL}/query/compare`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ states, metric }),
          });
          return res.json();
        },
      }),
      prepareDownload: tool({
        description: 'Prepare FIA data for download',
        parameters: z.object({
          states: z.array(z.string()),
          tables: z.array(z.string()).default(['PLOT', 'COND', 'TREE']),
        }),
        execute: async ({ states, tables }) => {
          const res = await fetch(`${process.env.PYFIA_API_URL}/downloads/prepare`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ states, tables }),
          });
          return res.json();
        },
      }),
    },
  });

  return result.toDataStreamResponse();
}
```

---

## Backend Architecture (FastAPI + pyFIA)

### Project Structure

```
backend/
├── src/
│   └── pyfia_api/
│       ├── __init__.py
│       ├── main.py              # FastAPI app
│       ├── config.py            # Settings
│       ├── api/
│       │   ├── __init__.py
│       │   ├── routes/
│       │   │   ├── chat.py      # Chat/streaming endpoints
│       │   │   ├── query.py     # Direct query endpoints
│       │   │   ├── downloads.py # Download preparation
│       │   │   └── health.py    # Health checks
│       │   └── deps.py          # Dependencies (DB, cache)
│       ├── services/
│       │   ├── __init__.py
│       │   ├── fia_service.py   # pyFIA wrapper
│       │   ├── agent.py         # LangChain agent
│       │   └── cache.py         # Redis caching
│       └── models/
│           ├── __init__.py
│           └── schemas.py       # Pydantic models
├── data/                        # FIA DuckDB files (gitignored)
├── downloads/                   # User downloads (gitignored)
├── tests/
├── pyproject.toml
├── Dockerfile
└── docker-compose.yml
```

### Main FastAPI Application

```python
# src/pyfia_api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .api.routes import chat, query, downloads, health
from .config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Pre-download common states
    from pyfia import download
    for state in settings.PRELOAD_STATES:
        try:
            download(state)
        except Exception as e:
            print(f"Warning: Could not preload {state}: {e}")
    yield
    # Shutdown: cleanup

app = FastAPI(
    title="pyFIA API",
    description="Natural language interface to USDA Forest Service FIA data",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health.router, tags=["Health"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(query.router, prefix="/api/v1/query", tags=["Query"])
app.include_router(downloads.router, prefix="/api/v1/downloads", tags=["Downloads"])
```

### Query Endpoints (Direct pyFIA Access)

```python
# src/pyfia_api/api/routes/query.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from ...services.fia_service import FIAService

router = APIRouter()
fia = FIAService()

class AreaQuery(BaseModel):
    states: list[str]
    land_type: str = "forest"
    grp_by: Optional[str] = None

class AreaResponse(BaseModel):
    states: list[str]
    land_type: str
    total_area_acres: float
    se_percent: float
    breakdown: Optional[list[dict]] = None
    source: str = "USDA Forest Service FIA (pyFIA validated)"

@router.post("/area", response_model=AreaResponse)
async def query_area(query: AreaQuery):
    """Query forest area for specified states."""
    try:
        result = await fia.query_area(
            states=query.states,
            land_type=query.land_type,
            grp_by=query.grp_by,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class VolumeQuery(BaseModel):
    states: list[str]
    by_species: bool = False
    tree_domain: Optional[str] = None

@router.post("/volume")
async def query_volume(query: VolumeQuery):
    """Query timber volume for specified states."""
    try:
        result = await fia.query_volume(
            states=query.states,
            by_species=query.by_species,
            tree_domain=query.tree_domain,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class BiomassQuery(BaseModel):
    states: list[str]
    land_type: str = "forest"
    by_species: bool = False

@router.post("/biomass")
async def query_biomass(query: BiomassQuery):
    """Query biomass and carbon for specified states."""
    try:
        result = await fia.query_biomass(
            states=query.states,
            land_type=query.land_type,
            by_species=query.by_species,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class CompareQuery(BaseModel):
    states: list[str]
    metric: str  # area, volume, biomass, tpa, mortality, growth

@router.post("/compare")
async def compare_states(query: CompareQuery):
    """Compare a metric across multiple states."""
    try:
        result = await fia.compare_states(
            states=query.states,
            metric=query.metric,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### FIA Service (pyFIA Wrapper)

```python
# src/pyfia_api/services/fia_service.py
from pyfia import download, FIA, area, volume, biomass, tpa, mortality, growth
from typing import Optional
import asyncio
from functools import lru_cache
import pandas as pd

class FIAService:
    """Service layer for pyFIA operations."""
    
    def __init__(self, cache_dir: str = "./data"):
        self.cache_dir = cache_dir
    
    @lru_cache(maxsize=50)
    def _get_db_path(self, state: str) -> str:
        """Download and cache state database."""
        return download(state, dir=self.cache_dir)
    
    async def query_area(
        self,
        states: list[str],
        land_type: str = "forest",
        grp_by: Optional[str] = None,
    ) -> dict:
        """Query forest area across states."""
        
        results = []
        
        for state in states:
            db_path = self._get_db_path(state)
            
            with FIA(db_path) as db:
                db.clip_by_state(state)
                db.clip_most_recent(eval_type="EXPALL")
                
                result_df = area(db, land_type=land_type, grp_by=grp_by)
                df = result_df.to_pandas()
                df['STATE'] = state
                results.append(df)
        
        combined = pd.concat(results, ignore_index=True)
        
        return {
            "states": states,
            "land_type": land_type,
            "total_area_acres": float(combined['ESTIMATE'].sum()),
            "se_percent": float(combined['SE_PERCENT'].mean()),
            "breakdown": combined.to_dict('records') if grp_by else None,
            "source": "USDA Forest Service FIA (pyFIA validated)",
        }
    
    async def query_volume(
        self,
        states: list[str],
        by_species: bool = False,
        tree_domain: Optional[str] = None,
    ) -> dict:
        """Query timber volume across states."""
        
        results = []
        
        for state in states:
            db_path = self._get_db_path(state)
            
            with FIA(db_path) as db:
                db.clip_by_state(state)
                db.clip_most_recent(eval_type="EXPVOL")
                
                result_df = volume(
                    db,
                    grp_by="SPCD" if by_species else None,
                    tree_domain=tree_domain,
                )
                df = result_df.to_pandas()
                df['STATE'] = state
                results.append(df)
        
        combined = pd.concat(results, ignore_index=True)
        total_vol = float(combined['ESTIMATE'].sum())
        
        return {
            "states": states,
            "total_volume_cuft": total_vol,
            "total_volume_billion_cuft": total_vol / 1e9,
            "se_percent": float(combined['SE_PERCENT'].mean()),
            "by_species": combined.to_dict('records') if by_species else None,
            "source": "USDA Forest Service FIA (pyFIA validated)",
        }
    
    async def query_biomass(
        self,
        states: list[str],
        land_type: str = "forest",
        by_species: bool = False,
    ) -> dict:
        """Query biomass and carbon stocks."""
        
        results = []
        
        for state in states:
            db_path = self._get_db_path(state)
            
            with FIA(db_path) as db:
                db.clip_by_state(state)
                db.clip_most_recent(eval_type="EXPVOL")
                
                result_df = biomass(db, land_type=land_type, by_species=by_species)
                df = result_df.to_pandas()
                df['STATE'] = state
                results.append(df)
        
        combined = pd.concat(results, ignore_index=True)
        total_biomass = float(combined['ESTIMATE'].sum())
        
        return {
            "states": states,
            "land_type": land_type,
            "total_biomass_tons": total_biomass,
            "carbon_mmt": total_biomass * 0.5 / 1e6,  # Standard conversion
            "se_percent": float(combined['SE_PERCENT'].mean()),
            "by_species": combined.to_dict('records') if by_species else None,
            "source": "USDA Forest Service FIA (pyFIA validated)",
        }
    
    async def compare_states(
        self,
        states: list[str],
        metric: str,
    ) -> dict:
        """Compare a metric across states."""
        
        metric_funcs = {
            "area": (area, "EXPALL"),
            "volume": (volume, "EXPVOL"),
            "biomass": (biomass, "EXPVOL"),
            "tpa": (tpa, "EXPVOL"),
            "mortality": (mortality, "EXPMORT"),
            "growth": (growth, "EXPGROW"),
        }
        
        if metric not in metric_funcs:
            raise ValueError(f"Unknown metric: {metric}")
        
        func, eval_type = metric_funcs[metric]
        results = []
        
        for state in states:
            try:
                db_path = self._get_db_path(state)
                
                with FIA(db_path) as db:
                    db.clip_by_state(state)
                    db.clip_most_recent(eval_type=eval_type)
                    
                    result_df = func(db)
                    df = result_df.to_pandas()
                    
                    results.append({
                        "state": state,
                        "estimate": float(df['ESTIMATE'].sum()),
                        "se_percent": float(df['SE_PERCENT'].mean()),
                    })
            except Exception as e:
                results.append({
                    "state": state,
                    "estimate": None,
                    "se_percent": None,
                    "error": str(e),
                })
        
        # Sort by estimate descending
        results.sort(key=lambda x: x.get('estimate') or 0, reverse=True)
        
        return {
            "metric": metric,
            "states": results,
            "source": "USDA Forest Service FIA (pyFIA validated)",
        }
```

### Streaming Chat Endpoint

```python
# src/pyfia_api/api/routes/chat.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import AsyncGenerator
import json

from ...services.agent import FIAAgent

router = APIRouter()
agent = FIAAgent()

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]

@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """Stream chat responses using Vercel AI SDK Data Stream Protocol."""
    
    async def generate() -> AsyncGenerator[str, None]:
        async for chunk in agent.stream(request.messages):
            # Format for Vercel AI SDK Data Stream Protocol
            if chunk["type"] == "text":
                yield f'0:{json.dumps(chunk["content"])}\n'
            elif chunk["type"] == "tool_call":
                yield f'9:{json.dumps(chunk)}\n'
            elif chunk["type"] == "tool_result":
                yield f'a:{json.dumps(chunk)}\n'
            elif chunk["type"] == "finish":
                yield f'd:{json.dumps({"finishReason": "stop"})}\n'
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
```

---

## Deployment

### Docker Compose (Self-Hosted)

```yaml
# docker-compose.yml
version: '3.8'

services:
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - BACKEND_URL=http://backend:8000
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    depends_on:
      - backend

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - REDIS_URL=redis://redis:6379
      - CORS_ORIGINS=http://localhost:3000,https://yourdomain.com
    volumes:
      - fia_data:/app/data
      - downloads:/app/downloads
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  fia_data:
  downloads:
  redis_data:
```

### Frontend Dockerfile

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS base

FROM base AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable pnpm && pnpm install --frozen-lockfile

FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN corepack enable pnpm && pnpm build

FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
```

### Backend Dockerfile

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Copy application
COPY src ./src

# Create data directories
RUN mkdir -p /app/data /app/downloads

EXPOSE 8000

CMD ["uvicorn", "pyfia_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Domain & Hosting Options

### Option 1: Vercel (Frontend) + Railway/Fly.io (Backend)

```
yourdomain.com (Vercel)
├── Next.js frontend
├── Edge functions for routing
└── Automatic HTTPS & CDN

api.yourdomain.com (Railway/Fly.io)
├── FastAPI backend
├── pyFIA + DuckDB
└── Persistent storage for FIA data
```

### Option 2: Single VPS (DigitalOcean/Linode/Hetzner)

```
yourdomain.com (nginx reverse proxy)
├── :3000 → Next.js frontend
├── :8000 → FastAPI backend
└── Let's Encrypt SSL
```

### Option 3: Cloud Run (GCP)

```
yourdomain.com (Cloud Run)
├── Frontend service (Next.js)
├── Backend service (FastAPI)
├── Cloud Storage (FIA data)
└── Memorystore (Redis cache)
```

---

## Cost Estimates

| Component | Option | Monthly Cost |
|-----------|--------|--------------|
| Frontend (Vercel) | Pro | $20 |
| Backend (Railway) | Developer | $5-20 |
| Backend (Fly.io) | 2x shared-cpu | $10-20 |
| Claude API | Usage-based | $50-200* |
| Redis (Upstash) | Free tier | $0 |
| Domain | Annual | ~$12/year |
| **Total** | | **$85-250/mo** |

*Claude costs depend heavily on usage volume

---

## Next Steps

1. **Initialize the monorepo**:
   ```bash
   mkdir pyfia-agent && cd pyfia-agent
   pnpm init
   # Set up Next.js frontend
   npx create-next-app@latest frontend --typescript --tailwind --app
   # Set up Python backend
   cd .. && mkdir backend && cd backend
   uv init
   ```

2. **Install shadcn/ui**:
   ```bash
   cd frontend
   npx shadcn@latest init
   npx shadcn@latest add button card input textarea scroll-area avatar badge
   ```

3. **Set up Vercel AI SDK**:
   ```bash
   pnpm add ai @ai-sdk/anthropic @ai-sdk/react
   ```

4. **Build the chat interface** using the components above

5. **Deploy** to your preferred hosting

Would you like me to scaffold out the complete project structure, or dive deeper into any specific component?
