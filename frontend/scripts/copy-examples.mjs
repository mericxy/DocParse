import { copyFile, mkdir, rm } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const filenames = [
  "time-card-01.pdf",
  "time-card-02.pdf",
  "time-card-03.pdf",
  "time-card-04.pdf",
  "payroll-01.pdf",
  "payroll-02.pdf",
  "payroll-03.pdf",
  "payroll-04.pdf",
];

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const sourceDirectory = resolve(scriptDirectory, "../../exemplos");
const targetDirectory = resolve(scriptDirectory, "../public/examples");

await rm(targetDirectory, { recursive: true, force: true });
await mkdir(targetDirectory, { recursive: true });

for (const filename of filenames) {
  await copyFile(
    resolve(sourceDirectory, filename),
    resolve(targetDirectory, filename),
  );
}
