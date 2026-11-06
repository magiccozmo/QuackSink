const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": "no-store"
};

const PUBLIC_LABELS = {
  session_start: "Started a new game session",
  heartbeat: "Still active",
  difficulty_easy: "Selected Easy mode",
  difficulty_normal: "Selected Normal mode",
  difficulty_spiffy_challenge: "Selected Spiffy Challenge",
  achievement_bucket_theft: "Market Mischief",
  achievement_naz_guard_death: "Unexpected Justice",
  achievement_vault_clip: "Unexpected Shortcut",
  achievement_lout_guard_death: "Inn Business Settled",
  achievement_hellgs_escape: "The Great Escape",
  achievement_caravan_chest_first_loot: "Hidden Cache",
  troll_cave_pineapple_exit: "Pineapple Getaway",
  quest_accepted: "New Adventure",
  quest_completed: "Quest Complete",
  kart_lotta_befriended: "Market Friendship",
  carriage_unlocked: "Road Ahead",
  cozmo_finale: "Part One Reached",
  cozmo_encounter_bucket: "Cozmo Encounter #1",
  cozmo_encounter_naz: "Cozmo Encounter #2",
  cozmo_encounter_vault_clip: "Cozmo Encounter #3",
  cozmo_encounter_lout_guard_death: "Cozmo Encounter #4",
  cozmo_encounter_hellgs_escape: "Cozmo Encounter #5",
  cozmo_encounter_caravan_chest: "Cozmo Encounter #6",
  cozmo_encounter_scenic_overlook: "Cozmo Encounter #7",
  cozmo_encounter_hellgs_save_return: "Cozmo Encounter #8",
  cozmo_encounter_hellgs_first_hint: "Cozmo Encounter #9",
  cozmo_encounter_hellgs_final_hint: "Cozmo Encounter #10",
  cozmo_encounter_hellgs_spoiler_hint: "Cozmo Encounter #11",
  cozmo_encounter_other: "Cozmo Encounter #12",
  potion_crafted: "Brewmaster",
  soup_cooked: "Kitchen Magic",
  soup_consumed: "Soup Power",
  scenic_overlook: "Admired View",
  spiffy_challenge_started: "Spiffy Challenge started",
  hellgs_challenge_started: "HELLgs challenge started",
  hellgs_game_over: "HELLgs challenge ended",
  game_saved: "Game Saved",
  save_loaded: "Save Loaded"
};

const ACHIEVEMENT_EVENTS = new Set([
  "achievement_bucket_theft", "achievement_naz_guard_death",
  "achievement_vault_clip", "achievement_lout_guard_death",
  "achievement_hellgs_escape", "achievement_caravan_chest_first_loot",
  "troll_cave_pineapple_exit", "quest_completed", "carriage_unlocked",
  "cozmo_finale", "potion_crafted", "soup_cooked", "scenic_overlook",
  "hellgs_challenge_started", "hellgs_game_over", "kart_lotta_befriended"
]);
const ALLOWED_EVENTS = new Set([
  ...Object.keys(PUBLIC_LABELS), "area_discovered", "cozmo_encounter"
]);

function respond(data, status = 200) {
  return new Response(JSON.stringify(data), {status, headers:CORS_HEADERS});
}
function timestamp() { return new Date().toISOString(); }
function cleanLocation(value, maxLength) {
  if (typeof value !== "string") return "";
  return value.replace(/[\u0000-\u001f\u007f]/g, "").trim().slice(0, maxLength);
}
function cloudflareLocation(request) {
  const country = cleanLocation(request.cf?.country, 24);
  const city = cleanLocation(request.cf?.city, 64);
  if (country && city) return country + " · " + city;
  return country || "Unknown";
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") return new Response(null, {status:204, headers:CORS_HEADERS});
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";

    try {
      if (path === "/health" && request.method === "GET") {
        const result = await env.DB.prepare(
          "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).all();
        return respond({status:"connected", database:"sgg-global-usage", tables:result.results.map(row => row.name)});
      }

      // This display lookup does not create a session or event record.
      if (path === "/location" && request.method === "GET") {
        const country = cleanLocation(request.cf?.country, 24);
        const city = cleanLocation(request.cf?.city, 64);
        return respond({country:country || "Unknown", city});
      }

      if (path === "/session" && request.method === "POST") {
        let body;
        try { body = await request.json(); } catch (_) { return respond({error:"Invalid JSON"},400); }
        const gameVersion = String(body.game_version || "").trim();
        const difficulty = String(body.difficulty || "").trim();
        if (!/^SGGG\d+(?:\.\d+)?$/i.test(gameVersion) || gameVersion.length > 40)
          return respond({error:"Invalid game_version"},400);
        if (!["easy","normal","spiffy_challenge"].includes(difficulty))
          return respond({error:"Invalid difficulty"},400);

        // Consent is explicit. Archived clients without the flag are anonymous by default.
        const shareLocation = body.share_location === true;
        const location = shareLocation ? cloudflareLocation(request) : "ANONYMOUS";
        const sessionId = crypto.randomUUID();
        const startedAt = timestamp();
        await env.DB.prepare(
          `INSERT INTO sessions (session_id,game_version,difficulty,region,started_at)
           VALUES (?,?,?,?,?)`
        ).bind(sessionId,gameVersion,difficulty,location,startedAt).run();
        await env.DB.prepare(
          `INSERT INTO events (session_id,event_type,description,occurred_at)
           VALUES (?,?,?,?)`
        ).bind(sessionId,"session_start",PUBLIC_LABELS.session_start,startedAt).run();
        return respond({status:"created",session_id:sessionId,started_at:startedAt,location_shared:shareLocation},201);
      }

      if (path === "/event" && request.method === "POST") {
        let body;
        try { body = await request.json(); } catch (_) { return respond({error:"Invalid JSON"},400); }
        const sessionId = String(body.session_id || "").trim();
        const eventType = String(body.event_type || "").trim();
        if (!/^[0-9a-f-]{36}$/i.test(sessionId)) return respond({error:"Invalid session_id"},400);
        if (!ALLOWED_EVENTS.has(eventType)) return respond({error:"Event type is not approved"},400);

        const session = await env.DB.prepare(
          "SELECT session_id FROM sessions WHERE session_id=?"
        ).bind(sessionId).first();
        if (!session) return respond({error:"Session not found"},404);

        const recent = await env.DB.prepare(
          `SELECT COUNT(*) AS total FROM events
           WHERE session_id=? AND occurred_at >= ?`
        ).bind(sessionId,new Date(Date.now()-60000).toISOString()).first();
        if (Number(recent?.total || 0) >= 30)
          return respond({error:"Session event rate limit reached"},429);

        if (eventType === "heartbeat") {
          const recentHeartbeat = await env.DB.prepare(
            `SELECT occurred_at FROM events WHERE session_id=? AND event_type='heartbeat'
             ORDER BY event_id DESC LIMIT 1`
          ).bind(sessionId).first();
          if (recentHeartbeat && Date.now()-Date.parse(recentHeartbeat.occurred_at) < 60000)
            return respond({status:"ignored",reason:"Heartbeat received too recently"});
        }

        if (ACHIEVEMENT_EVENTS.has(eventType)) {
          const prior = await env.DB.prepare(
            "SELECT event_id FROM events WHERE session_id=? AND event_type=? LIMIT 1"
          ).bind(sessionId,eventType).first();
          if (prior) return respond({status:"ignored",reason:"This achievement was already recorded for the session"});
        }

        let description = PUBLIC_LABELS[eventType];
        if (eventType === "area_discovered" || eventType === "cozmo_encounter") {
          const count = await env.DB.prepare(
            "SELECT COUNT(*) AS total FROM events WHERE session_id=? AND event_type=?"
          ).bind(sessionId,eventType).first();
          const number = Number(count?.total || 0) + 1;
          description = eventType === "area_discovered" ? `Area Discovery #${number}` : `Cozmo Encounter #${number}`;
        }
        if (!description) return respond({error:"Event type is not approved"},400);
        const occurredAt = timestamp();
        await env.DB.prepare(
          `INSERT INTO events (session_id,event_type,description,occurred_at)
           VALUES (?,?,?,?)`
        ).bind(sessionId,eventType,description,occurredAt).run();
        return respond({status:"recorded",event_type:eventType,description,occurred_at:occurredAt},201);
      }

      if (path === "/log" && request.method === "GET") {
        const rawLimit = Number(url.searchParams.get("limit") || 50);
        const limit = Number.isInteger(rawLimit) ? Math.min(Math.max(rawLimit,1),50) : 50;
        const rawBefore = url.searchParams.get("before");
        let before = null;
        if (rawBefore !== null) {
          if (!/^\d+$/.test(rawBefore) || !Number.isSafeInteger(Number(rawBefore)) || Number(rawBefore) < 1)
            return respond({error:"Invalid before cursor"},400);
          before = Number(rawBefore);
        }
        const where = [
          "sessions.game_version NOT LIKE 'TEST%'",
          "(events.event_type <> 'heartbeat' OR events.event_id = (SELECT MAX(h.event_id) FROM events h WHERE h.session_id=events.session_id AND h.event_type='heartbeat'))"
        ];
        const bindings = [];
        if (before !== null) { where.push("events.event_id < ?"); bindings.push(before); }
        bindings.push(limit+1);
        const result = await env.DB.prepare(
          `SELECT events.event_id, substr(events.session_id,1,8) AS session,
                  events.event_type,events.description,events.occurred_at,
                  sessions.game_version,sessions.difficulty,sessions.region,
                  CAST(MAX(0,ROUND((julianday(events.occurred_at)-julianday(sessions.started_at))*86400)) AS INTEGER) AS session_duration_seconds
           FROM events INNER JOIN sessions ON events.session_id=sessions.session_id
           WHERE ${where.join(" AND ")}
           ORDER BY events.event_id DESC LIMIT ?`
        ).bind(...bindings).all();
        const rows = result.results || [];
        const hasMore = rows.length > limit;
        const events = rows.slice(0,limit);
        const nextCursor = events.length ? String(events[events.length-1].event_id) : null;
        return respond({status:"ok",count:events.length,limit,has_more:hasMore,next_cursor:nextCursor,events});
      }

      return respond({error:"Not found",available_endpoints:["GET /health","GET /location","POST /session","POST /event","GET /log"]},404);
    } catch (_) {
      return respond({error:"Request failed"},500);
    }
  }
};
