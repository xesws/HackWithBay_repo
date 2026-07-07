// Verify web/src/sample_verdict.json satisfies the C3 acceptance criteria:
//   - the four §4.2 node colors are all present (green, red, gray, orange)
//   - every claim node (claim:*) resolves to a claim with populated evidence
//     (type + path), i.e. it is a clickable "evidence node"
// Exits non-zero on failure so `npm run check:sample` can gate.
import { readFileSync } from "node:fs";

const url = new URL("../src/sample_verdict.json", import.meta.url);
const v = JSON.parse(readFileSync(url, "utf8"));

const errors = [];

const REQUIRED_COLORS = ["green", "red", "gray", "orange"];
const colors = new Set((v.graph?.nodes ?? []).map((n) => n.color));
for (const c of REQUIRED_COLORS) {
  if (!colors.has(c)) errors.push(`missing node color: ${c}`);
}

const claimsById = new Map((v.claims ?? []).map((c) => [c.cid, c]));
const claimNodes = (v.graph?.nodes ?? []).filter((n) => String(n.id).startsWith("claim:"));
let evidenceNodes = 0;
for (const n of claimNodes) {
  const cid = String(n.id).slice("claim:".length);
  const claim = claimsById.get(cid);
  if (!claim) {
    errors.push(`claim node ${n.id} has no matching claims[${cid}]`);
    continue;
  }
  const ev = claim.evidence;
  if (!ev || !ev.type || !Array.isArray(ev.path)) {
    errors.push(`claim ${cid} missing evidence (type/path)`);
    continue;
  }
  evidenceNodes++;
}

// Statuses present (sanity that all three §4.2 statuses are exercised)
const statuses = new Set((v.claims ?? []).map((c) => c.status));

console.log("job_id:", v.job_id);
console.log("doc_score:", v.doc_score);
console.log("distinct node colors:", [...colors].sort().join(", "), `(count=${colors.size})`);
console.log("claim statuses:", [...statuses].sort().join(", "));
console.log("clickable evidence nodes (claim:* with evidence):", evidenceNodes, "/", claimNodes.length);
console.log("graph nodes:", (v.graph?.nodes ?? []).length, "edges:", (v.graph?.edges ?? []).length);

if (colors.size !== 4) errors.push(`expected exactly 4 distinct colors, got ${colors.size}`);
if (evidenceNodes < 1) errors.push("no clickable evidence nodes found");

if (errors.length) {
  console.error("\nCHECK FAILED:");
  for (const e of errors) console.error("  - " + e);
  process.exit(1);
}
console.log("\nCHECK PASSED ✓");
