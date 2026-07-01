#!/usr/bin/env node

// ─────────────────────────────────────────────────────────────
//  Hashnode MCP Server
//  Exposes tools: publish_post, create_draft, search_tags,
//                 list_drafts, get_publication
//  Requires env:  HASHNODE_PAT, HASHNODE_PUBLICATION_ID
// ─────────────────────────────────────────────────────────────

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const HASHNODE_GQL = "https://gql.hashnode.com";

// ── Helpers ──────────────────────────────────────────────────

function env(name) {
  const v = process.env[name];
  if (!v) throw new Error(`Missing required env var: ${name}`);
  return v;
}

async function gql(query, variables = {}) {
  const res = await fetch(HASHNODE_GQL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: env("HASHNODE_PAT"),
    },
    body: JSON.stringify({ query, variables }),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Hashnode HTTP ${res.status}: ${body}`);
  }
  const json = await res.json();
  if (json.errors) {
    throw new Error(
      `Hashnode API error: ${json.errors.map((e) => e.message).join("; ")}`
    );
  }
  return json.data;
}

/** Resolve an array of human-readable tag slugs into Hashnode tag objects with IDs. */
async function resolveTags(slugs) {
  if (!slugs || slugs.length === 0) return [];
  const resolved = [];
  for (const raw of slugs) {
    const slug = raw.toLowerCase().replace(/\s+/g, "-");
    try {
      const data = await gql(
        `query Tag($slug: String!) { tag(slug: $slug) { id name slug } }`,
        { slug }
      );
      if (data.tag) resolved.push(data.tag);
    } catch {
      // tag not found — skip silently
    }
  }
  return resolved;
}

/** Build the common input fields shared by publish and draft mutations. */
function buildPostInput(args, tags) {
  const input = {
    publicationId: env("HASHNODE_PUBLICATION_ID"),
    title: args.title,
    contentMarkdown: args.contentMarkdown,
  };
  if (args.subtitle) input.subtitle = args.subtitle;
  if (args.slug) input.slug = args.slug;
  if (args.coverImageURL)
    input.coverImageOptions = { coverImageURL: args.coverImageURL };
  if (tags.length > 0)
    input.tags = tags.map((t) => ({ id: t.id, name: t.name, slug: t.slug }));
  return input;
}

// ── Tool definitions ─────────────────────────────────────────

const TOOLS = [
  {
    name: "hashnode_publish_post",
    description:
      "Publish a blog post to Hashnode immediately. Accepts markdown content, title, optional subtitle, slug, tags (as slugs — resolved automatically), and cover image URL. Returns the live post URL.",
    inputSchema: {
      type: "object",
      properties: {
        title: { type: "string", description: "Post title" },
        contentMarkdown: {
          type: "string",
          description: "Full markdown body of the blog post",
        },
        subtitle: { type: "string", description: "Post subtitle (optional)" },
        slug: {
          type: "string",
          description:
            'URL-friendly slug, e.g. "solving-cors-in-fastapi" (auto-generated if omitted)',
        },
        tags: {
          type: "array",
          items: { type: "string" },
          description:
            'Tag slugs, e.g. ["javascript","web-development"]. Resolved to Hashnode tag IDs automatically.',
        },
        coverImageURL: {
          type: "string",
          description: "URL of the cover image (optional)",
        },
      },
      required: ["title", "contentMarkdown"],
    },
  },
  {
    name: "hashnode_create_draft",
    description:
      "Create a draft blog post on Hashnode (not published). Same inputs as publish. Returns draft ID.",
    inputSchema: {
      type: "object",
      properties: {
        title: { type: "string", description: "Post title" },
        contentMarkdown: {
          type: "string",
          description: "Full markdown body of the blog post",
        },
        subtitle: { type: "string", description: "Post subtitle (optional)" },
        slug: { type: "string", description: "URL-friendly slug (optional)" },
        tags: {
          type: "array",
          items: { type: "string" },
          description: "Tag slugs (resolved automatically)",
        },
        coverImageURL: {
          type: "string",
          description: "Cover image URL (optional)",
        },
      },
      required: ["title", "contentMarkdown"],
    },
  },
  {
    name: "hashnode_search_tags",
    description:
      "Look up a Hashnode tag by slug. Returns the tag ID, name, slug, and post count. Use this to verify tags exist before publishing.",
    inputSchema: {
      type: "object",
      properties: {
        slug: {
          type: "string",
          description:
            'Tag slug to look up, e.g. "javascript", "web-development"',
        },
      },
      required: ["slug"],
    },
  },
  {
    name: "hashnode_list_drafts",
    description:
      "List the 20 most recent drafts on your Hashnode publication.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "hashnode_get_publication",
    description:
      "Get your Hashnode publication info (title, URL, about) and the 5 most recent published posts. Useful for verifying credentials are working.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
];

// ── Tool handlers ────────────────────────────────────────────

async function handleTool(name, args) {
  switch (name) {
    case "hashnode_publish_post": {
      const tags = await resolveTags(args.tags);
      const input = buildPostInput(args, tags);
      const data = await gql(
        `mutation Publish($input: PublishPostInput!) {
          publishPost(input: $input) {
            post { id title slug url }
          }
        }`,
        { input }
      );
      const post = data.publishPost.post;
      return {
        message: "Post published successfully.",
        post,
        tagsResolved: tags.length,
        tagsRequested: (args.tags || []).length,
      };
    }

    case "hashnode_create_draft": {
      const tags = await resolveTags(args.tags);
      const input = buildPostInput(args, tags);
      const data = await gql(
        `mutation Draft($input: CreateDraftInput!) {
          createDraft(input: $input) {
            draft { id title slug }
          }
        }`,
        { input }
      );
      const draft = data.createDraft.draft;
      return {
        message: "Draft created successfully. Edit it in your Hashnode dashboard.",
        draft,
        tagsResolved: tags.length,
        tagsRequested: (args.tags || []).length,
      };
    }

    case "hashnode_search_tags": {
      const slug = (args.slug || "").toLowerCase().replace(/\s+/g, "-");
      const data = await gql(
        `query Tag($slug: String!) {
          tag(slug: $slug) { id name slug postsCount }
        }`,
        { slug }
      );
      if (!data.tag) return { found: false, slug, message: `No tag found for slug "${slug}".` };
      return { found: true, tag: data.tag };
    }

    case "hashnode_list_drafts": {
      const pubId = env("HASHNODE_PUBLICATION_ID");
      const data = await gql(
        `query Drafts($id: ObjectId!) {
          publication(id: $id) {
            drafts(first: 20) {
              edges { node { id title slug updatedAt } }
            }
          }
        }`,
        { id: pubId }
      );
      const drafts = data.publication.drafts.edges.map((e) => e.node);
      return { count: drafts.length, drafts };
    }

    case "hashnode_get_publication": {
      const pubId = env("HASHNODE_PUBLICATION_ID");
      const data = await gql(
        `query Pub($id: ObjectId!) {
          publication(id: $id) {
            id title displayTitle url
            about { markdown }
            posts(first: 5) {
              edges { node { title slug url publishedAt } }
            }
          }
        }`,
        { id: pubId }
      );
      const pub = data.publication;
      return {
        id: pub.id,
        title: pub.title,
        displayTitle: pub.displayTitle,
        url: pub.url,
        about: pub.about?.markdown || "",
        recentPosts: pub.posts.edges.map((e) => e.node),
      };
    }

    default:
      throw new Error(`Unknown tool: ${name}`);
  }
}

// ── Server bootstrap ─────────────────────────────────────────

const server = new Server(
  { name: "hashnode", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(
  { method: "tools/list" },
  async () => ({ tools: TOOLS })
);

server.setRequestHandler({ method: "tools/call" }, async (request) => {
  const { name, arguments: args } = request.params;
  try {
    const result = await handleTool(name, args || {});
    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  } catch (err) {
    return {
      content: [{ type: "text", text: `Error: ${err.message}` }],
      isError: true,
    };
  }
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  process.stderr.write("Hashnode MCP server running on stdio\n");
}

main().catch((err) => {
  process.stderr.write(`Fatal: ${err.message}\n`);
  process.exit(1);
});