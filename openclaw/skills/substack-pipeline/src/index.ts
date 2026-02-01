/**
 * OpenClaw Skill: Substack Pipeline
 *
 * This skill provides tools for processing Substack archives using the
 * LangChain-powered pipeline. It wraps the Python pipeline modules and
 * exposes them as OpenClaw tools.
 */

import { defineSkill, defineTool, z } from "@openclaw/sdk";
import { spawn } from "child_process";
import { join, resolve } from "path";

// Get project root (3 levels up from this file)
const PROJECT_ROOT = resolve(__dirname, "../../..");

/**
 * Execute a Python pipeline command
 */
async function runPipeline(
  command: string,
  args: Record<string, unknown> = {}
): Promise<{ success: boolean; output: string; error?: string }> {
  return new Promise((resolve) => {
    const cliArgs = ["-m", "pipeline.main", command];

    // Convert args to CLI flags
    for (const [key, value] of Object.entries(args)) {
      if (value !== undefined && value !== null) {
        if (typeof value === "boolean") {
          if (value) cliArgs.push(`--${key}`);
        } else if (Array.isArray(value)) {
          cliArgs.push(`--${key}`, value.join(","));
        } else {
          cliArgs.push(`--${key}`, String(value));
        }
      }
    }

    const proc = spawn("python3", cliArgs, {
      cwd: PROJECT_ROOT,
      env: { ...process.env },
    });

    let stdout = "";
    let stderr = "";

    proc.stdout.on("data", (data) => {
      stdout += data.toString();
    });

    proc.stderr.on("data", (data) => {
      stderr += data.toString();
    });

    proc.on("close", (code) => {
      if (code === 0) {
        resolve({ success: true, output: stdout });
      } else {
        resolve({ success: false, output: stdout, error: stderr });
      }
    });

    proc.on("error", (err) => {
      resolve({ success: false, output: "", error: err.message });
    });
  });
}

/**
 * Tool: Load Substack posts
 */
const loadTool = defineTool({
  name: "substack.load",
  description: "Load Substack posts from a directory",
  parameters: z.object({
    input_dir: z
      .string()
      .optional()
      .describe("Path to input directory (default: data/raw)"),
    formats: z
      .array(z.enum(["md", "html", "json"]))
      .optional()
      .describe("File formats to load (default: all)"),
  }),
  execute: async ({ input_dir, formats }) => {
    const args: Record<string, unknown> = {};
    if (input_dir) args.input = input_dir;
    if (formats) args.formats = formats;

    const result = await runPipeline("load", args);

    if (result.success) {
      return {
        status: "success",
        message: "Posts loaded successfully",
        details: result.output,
      };
    } else {
      return {
        status: "error",
        message: "Failed to load posts",
        error: result.error,
      };
    }
  },
});

/**
 * Tool: Process documents
 */
const processTool = defineTool({
  name: "substack.process",
  description: "Process loaded posts into chunks for vector embedding",
  parameters: z.object({
    chunk_size: z.number().optional().describe("Size of text chunks (default: 1000)"),
    chunk_overlap: z
      .number()
      .optional()
      .describe("Overlap between chunks (default: 200)"),
  }),
  execute: async ({ chunk_size, chunk_overlap }) => {
    const args: Record<string, unknown> = {};
    if (chunk_size) args["chunk-size"] = chunk_size;
    if (chunk_overlap) args["chunk-overlap"] = chunk_overlap;

    const result = await runPipeline("process", args);

    if (result.success) {
      return {
        status: "success",
        message: "Documents processed successfully",
        details: result.output,
      };
    } else {
      return {
        status: "error",
        message: "Failed to process documents",
        error: result.error,
      };
    }
  },
});

/**
 * Tool: Generate summaries
 */
const summarizeTool = defineTool({
  name: "substack.summarize",
  description: "Generate AI summaries for processed posts",
  parameters: z.object({
    model: z.string().optional().describe("LLM model to use"),
    max_posts: z.number().optional().describe("Maximum posts to summarize"),
    input: z.string().optional().describe("Input directory"),
  }),
  execute: async ({ model, max_posts, input }) => {
    const args: Record<string, unknown> = {};
    if (model) args.model = model;
    if (max_posts) args["max-posts"] = max_posts;
    if (input) args.input = input;

    const result = await runPipeline("summarize", args);

    if (result.success) {
      return {
        status: "success",
        message: "Summaries generated successfully",
        details: result.output,
      };
    } else {
      return {
        status: "error",
        message: "Failed to generate summaries",
        error: result.error,
      };
    }
  },
});

/**
 * Tool: Extract glossary
 */
const glossaryTool = defineTool({
  name: "substack.glossary",
  description: "Extract glossary terms from posts",
  parameters: z.object({
    min_occurrences: z
      .number()
      .optional()
      .describe("Minimum term occurrences (default: 2)"),
    categories: z.array(z.string()).optional().describe("Term categories to extract"),
    input: z.string().optional().describe("Input directory"),
  }),
  execute: async ({ min_occurrences, categories, input }) => {
    const args: Record<string, unknown> = {};
    if (min_occurrences) args["min-occurrences"] = min_occurrences;
    if (categories) args.categories = categories;
    if (input) args.input = input;

    const result = await runPipeline("glossary", args);

    if (result.success) {
      return {
        status: "success",
        message: "Glossary extracted successfully",
        details: result.output,
      };
    } else {
      return {
        status: "error",
        message: "Failed to extract glossary",
        error: result.error,
      };
    }
  },
});

/**
 * Tool: Extract entities
 */
const entitiesTool = defineTool({
  name: "substack.entities",
  description: "Extract named entities from posts",
  parameters: z.object({
    entity_types: z
      .array(
        z.enum([
          "people",
          "organizations",
          "places",
          "concepts",
          "technical",
          "events",
          "works",
          "acronyms",
        ])
      )
      .optional()
      .describe("Entity types to extract"),
    input: z.string().optional().describe("Input directory or file"),
  }),
  execute: async ({ entity_types, input }) => {
    // Use the entity extraction script
    const args = [join(PROJECT_ROOT, "scripts/entity_glossary.py")];
    if (input) args.push(input);
    if (entity_types) {
      args.push("--types", entity_types.join(","));
    }

    return new Promise((resolve) => {
      const proc = spawn("python3", args, {
        cwd: PROJECT_ROOT,
        env: { ...process.env },
      });

      let stdout = "";
      let stderr = "";

      proc.stdout.on("data", (data) => {
        stdout += data.toString();
      });

      proc.stderr.on("data", (data) => {
        stderr += data.toString();
      });

      proc.on("close", (code) => {
        if (code === 0) {
          resolve({
            status: "success",
            message: "Entities extracted successfully",
            details: stdout,
          });
        } else {
          resolve({
            status: "error",
            message: "Failed to extract entities",
            error: stderr,
          });
        }
      });
    });
  },
});

/**
 * Tool: Semantic search
 */
const searchTool = defineTool({
  name: "substack.search",
  description: "Perform semantic search across the archive",
  parameters: z.object({
    query: z.string().describe("Search query"),
    top_k: z.number().optional().describe("Number of results (default: 5)"),
  }),
  execute: async ({ query, top_k }) => {
    const args: Record<string, unknown> = { query };
    if (top_k) args["top-k"] = top_k;

    const result = await runPipeline("search", args);

    if (result.success) {
      return {
        status: "success",
        message: "Search completed",
        results: result.output,
      };
    } else {
      return {
        status: "error",
        message: "Search failed",
        error: result.error,
      };
    }
  },
});

/**
 * Tool: Generate static site
 */
const generateSiteTool = defineTool({
  name: "substack.generate-site",
  description: "Generate static site for GitHub Pages",
  parameters: z.object({
    output_dir: z.string().optional().describe("Output directory (default: site)"),
    input: z.string().optional().describe("Input directory"),
  }),
  execute: async ({ output_dir, input }) => {
    const args: Record<string, unknown> = {};
    if (output_dir) args.output = output_dir;
    if (input) args.input = input;

    const result = await runPipeline("site", args);

    if (result.success) {
      return {
        status: "success",
        message: "Site generated successfully",
        details: result.output,
        path: output_dir || "site",
      };
    } else {
      return {
        status: "error",
        message: "Failed to generate site",
        error: result.error,
      };
    }
  },
});

/**
 * Tool: Run full pipeline
 */
const runPipelineTool = defineTool({
  name: "substack.run",
  description: "Run the complete Substack processing pipeline",
  parameters: z.object({
    input: z.string().optional().describe("Input directory (default: data/raw)"),
    skip_summaries: z.boolean().optional().describe("Skip summary generation"),
    skip_glossary: z.boolean().optional().describe("Skip glossary extraction"),
    skip_site: z.boolean().optional().describe("Skip site generation"),
  }),
  execute: async ({ input, skip_summaries, skip_glossary, skip_site }) => {
    const args: Record<string, unknown> = {};
    if (input) args.input = input;
    if (skip_summaries) args["skip-summaries"] = true;
    if (skip_glossary) args["skip-glossary"] = true;
    if (skip_site) args["skip-site"] = true;

    const result = await runPipeline("run", args);

    if (result.success) {
      return {
        status: "success",
        message: "Pipeline completed successfully",
        details: result.output,
      };
    } else {
      return {
        status: "error",
        message: "Pipeline failed",
        error: result.error,
      };
    }
  },
});

/**
 * Define the skill with all tools
 */
export default defineSkill({
  name: "substack-pipeline",
  displayName: "Substack Pipeline",
  description:
    "Process Substack archives with AI-powered summaries, glossary extraction, and static site generation",
  version: "1.0.0",
  tools: [
    loadTool,
    processTool,
    summarizeTool,
    glossaryTool,
    entitiesTool,
    searchTool,
    generateSiteTool,
    runPipelineTool,
  ],
});
