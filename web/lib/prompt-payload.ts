import type { PromptInput } from "@/lib/types";

export interface ParsedPromptPayload {
  prompts: PromptInput[];
  normalizedText: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readString(value: unknown, fieldName: string, index: number) {
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`Prompt ${index + 1} is missing a valid "${fieldName}" string.`);
  }
  return value;
}

export function parsePromptPayload(source: string): ParsedPromptPayload {
  const trimmed = source.trim();
  if (!trimmed) {
    throw new Error("Paste a JSON array of prompts or an object with a \"prompts\" array.");
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch (error) {
    throw new Error(
      `Invalid JSON: ${error instanceof Error ? error.message : "unable to parse payload"}`,
    );
  }

  const rawPrompts = Array.isArray(parsed)
    ? parsed
    : isRecord(parsed) && Array.isArray(parsed.prompts)
      ? parsed.prompts
      : null;

  if (!rawPrompts) {
    throw new Error("Expected a JSON array of prompts or an object shaped like { \"prompts\": [...] }.");
  }

  const prompts = rawPrompts.map((item, index) => {
    if (!isRecord(item)) {
      throw new Error(`Prompt ${index + 1} must be a JSON object.`);
    }

    const prompt: PromptInput = {
      prompt_id: readString(item.prompt_id, "prompt_id", index),
      category: readString(item.category, "category", index),
      layer: readString(item.layer, "layer", index),
      content: readString(item.content, "content", index),
    };

    if (item.name !== undefined && item.name !== null) {
      prompt.name = readString(item.name, "name", index);
    }

    return prompt;
  });

  return {
    prompts,
    normalizedText: JSON.stringify(prompts, null, 2),
  };
}
