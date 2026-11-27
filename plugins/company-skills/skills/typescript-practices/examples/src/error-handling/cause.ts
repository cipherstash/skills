import { readFile } from "node:fs/promises";

export async function readConfig(path: string): Promise<string> {
  try {
    return await readFile(path, "utf8");
  } catch (error) {
    throw new Error(`reading config ${path}`, { cause: error });
  }
}
