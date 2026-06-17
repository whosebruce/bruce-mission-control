/**
 * Seed demo data so a fresh install has something to look at.
 * Bruce's bot roster — running under Hermes Agent on the Life of Bruce stack.
 * Run once with `npm run seed:demo`. Safe to re-run (upserts by id).
 */
import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

const AGENTS = [
  {
    id: "mira",
    name: "Mira",
    emoji: "🪞",
    role: "Knowledge / Orchestration",
    status: "working",
    tasksCompleted: 124,
    totalCost: 4.82,
    currentTask: "Drafting daily Mira digest into Obsidian",
  },
  {
    id: "apollo",
    name: "Apollo",
    emoji: "🎨",
    role: "Creative / Design",
    status: "idle",
    tasksCompleted: 38,
    totalCost: 1.91,
    currentTask: null,
  },
  {
    id: "otto",
    name: "Otto",
    emoji: "🔧",
    role: "Ops / Home",
    status: "online",
    tasksCompleted: 67,
    totalCost: 0.88,
    currentTask: "Heartbeat check on Helios services",
  },
  {
    id: "jade",
    name: "Jade",
    emoji: "🔭",
    role: "Research / Frontier Intel",
    status: "online",
    tasksCompleted: 22,
    totalCost: 1.05,
    currentTask: "Weekly frontier lab scan — OpenAI, Anthropic, xAI",
  },
];

const MISSIONS = [
  { agentId: "mira",   title: "Send Mira daily digest to Discord + Obsidian", status: "active",   priority: "high"   },
  { agentId: "jade",   title: "Frontier lab scan — week of YYYY-MM-DD",         status: "pending",  priority: "high"   },
  { agentId: "apollo", title: "Studio Futura brand kit — phase 2",              status: "active",   priority: "medium" },
  { agentId: "otto",   title: "Proxmox backup audit (192.168.88.7)",            status: "pending",  priority: "medium" },
  { agentId: "jade",   title: "Improve Nova — weekly meta-loop",                status: "active",   priority: "low"    },
];

const IDEAS = [
  {
    title: "Daily Mira digest → Discord thread + Obsidian note",
    description: "Each bot ends the day with a 5-bullet standup. Mira aggregates and posts.",
    source: "mira",
    status: "pending",
  },
  {
    title: "Frontier AI weekly — Obsidian brief from Jade",
    description: "What shipped from OpenAI / Anthropic / Google / xAI / Meta / Mistral / DeepSeek / Qwen.",
    source: "jade",
    status: "pending",
  },
  {
    title: "Studio Futura Etsy listing pack — Apollo batch",
    description: "Generate 1:1 logo, 21:9 banner, 2:3 pin variants for new SKUs.",
    source: "apollo",
    status: "pending",
  },
  {
    title: "Helios uptime dashboard card",
    description: "Surface Ollama / Open WebUI / SearXNG / helios-youtube / Whisper health on Mission Control.",
    source: "otto",
    status: "pending",
  },
  {
    title: "BruceWorks Pocket Class — closer sequence (Mira + Kimmy)",
    description: "Email + DM cadence for $25 v1 buyers → $50-75 v2 upsell.",
    source: "mira",
    status: "pending",
  },
];

async function main() {
  console.log("Seeding Bruce Mission Control demo data...");

  for (const a of AGENTS) {
    await prisma.agentState.upsert({
      where: { id: a.id },
      create: { ...a, lastActive: new Date() },
      update: { ...a, lastActive: new Date() },
    });
  }
  console.log(`  ${AGENTS.length} agents`);

  const existingMissions = await prisma.mission.count();
  if (existingMissions === 0) {
    for (const m of MISSIONS) {
      await prisma.mission.create({ data: { ...m, description: m.title } });
    }
    console.log(`  ${MISSIONS.length} missions`);
  } else {
    console.log(`  missions: already have ${existingMissions}, skipping`);
  }

  const existingIdeas = await prisma.idea.count();
  if (existingIdeas === 0) {
    for (const i of IDEAS) {
      await prisma.idea.create({ data: i });
    }
    console.log(`  ${IDEAS.length} ideas`);
  } else {
    console.log(`  ideas: already have ${existingIdeas}, skipping`);
  }

  console.log("Done. Open http://localhost:3000 to see the dashboard.");
}

main()
  .then(() => process.exit(0))
  .catch((e) => {
    console.error(e);
    process.exit(1);
  });