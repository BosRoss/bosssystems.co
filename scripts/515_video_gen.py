#!/usr/bin/env python3
"""
515 Scenic Cabins — AI Video Generator v7 (Kling V3 Pro + Audio Production).

Full production pipeline: Kling V3 Pro video generation → phone camera look →
format overlay (news/CCTV) → auto audio mix with SFX library → postable output.

Setup:
    echo "YOUR_FAL_KEY" > ~/.boss_secrets/fal_key

Pipeline (use these):
    python3 515_video_gen.py pipeline                  # Full pipeline status + what's needed
    python3 515_video_gen.py batch                     # Produce ALL ready ideas in sequence
    python3 515_video_gen.py clean                     # Remove dead videos from ready/
    python3 515_video_gen.py produce <idea_id>         # Produce single video (generate + overlay + audio)
    python3 515_video_gen.py test-overlay <idea_id>    # Test overlay without generating ($0)

Audio (motion-synced — no guessing):
    python3 515_video_gen.py sync-audio <idea_id>      # Re-analyze video + rebuild audio timing
    python3 515_video_gen.py retime <idea_id>          # Show current audio timing
    python3 515_video_gen.py retime <idea_id> 3=7.0    # Fine-tune layer 3 to 7.0s ($0)
    python3 515_video_gen.py preview <idea_id>         # Preview pre-gen audio plan (estimate)
    python3 515_video_gen.py sfx                       # List SFX library + coverage

Quality Gate:
    python3 515_video_gen.py review                    # Show all videos in review/
    python3 515_video_gen.py approve-video <idea_id>   # Move reviewed video to ready/
    python3 515_video_gen.py reject-video <idea_id> [reason]  # Reject + delete reviewed video

Ideas Bank:
    python3 515_video_gen.py ideas [category]          # Browse 100-idea bank
    python3 515_video_gen.py approve-idea <id> [...]   # Approve ideas for production
    python3 515_video_gen.py decline-idea <id> [...]   # Kill bad ideas

Management:
    python3 515_video_gen.py status
    python3 515_video_gen.py list
    python3 515_video_gen.py check <idea_id>
    python3 515_video_gen.py plates
"""

import json, os, sys, time, urllib.request, urllib.error, subprocess, re, tempfile
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

sys.stdout.reconfigure(line_buffering=True)

SCRIPTS = Path(__file__).parent
ROOT = SCRIPTS.parent
DATA_DIR = ROOT / "atlas_data" / "515"
RAW_DIR = DATA_DIR / "media" / "raw"
PLATES_DIR = DATA_DIR / "media" / "plates"
IDEAS_FILE = DATA_DIR / "video_ideas.json"
SECRETS = Path.home() / ".boss_secrets"
CT = ZoneInfo("America/Chicago")
READY_DIR = DATA_DIR / "media" / "ready"
REVIEW_DIR = DATA_DIR / "media" / "review"
REFBANK_DIR = PLATES_DIR / "reference_bank"
IDEAS_BANK_FILE = DATA_DIR / "ideas_bank.json"
PIPELINE_TARGET = 7

COMPOSITES_DIR = PLATES_DIR / "composites"
for d in [RAW_DIR, PLATES_DIR, READY_DIR, REVIEW_DIR, REFBANK_DIR, COMPOSITES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    FFMPEG = "ffmpeg"

KLING_ENDPOINT = "fal-ai/kling-video/v3/pro/image-to-video"
SFX_DIR = DATA_DIR / "media" / "sfx"
BACKUP_DIR = DATA_DIR / "media" / "noaudio_backup"
for d in [SFX_DIR, BACKUP_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────────────────────
# SFX LIBRARY — maps sound categories to files
# ──────────────────────────────────────────────────────────────
AMBIENT_MAP = {
    "dawn": "dawn_birds.mp3",
    "morning": "dawn_birds.mp3",
    "afternoon": "afternoon_nature.mp3",
    "evening": "ambient_night.mp3",
    "night": "ambient_night.mp3",
    "sunset": "afternoon_nature.mp3",
}

SOUND_KEYWORDS = {
    "slam": ("card_slam.mp3", -20),
    "slams": ("card_slam.mp3", -20),
    "crash": ("table_crash.mp3", -16),
    "flip": ("table_crash.mp3", -16),
    "flips": ("table_crash.mp3", -16),
    "splash": ("splash_large.mp3", -14),
    "splashing": ("fish_splash.mp3", -16),
    "launch": ("fish_splash.mp3", -14),
    "thud": ("heavy_thud.mp3", -16),
    "landing": ("heavy_thud.mp3", -16),
    "lands": ("heavy_thud.mp3", -15),
    "walk": ("footsteps_wood.mp3", -20),
    "walks": ("footsteps_wood.mp3", -20),
    "waddle": ("footsteps_wood.mp3", -22),
    "waddling": ("footsteps_wood.mp3", -22),
    "march": ("footsteps_wood.mp3", -18),
    "marching": ("footsteps_wood.mp3", -18),
    "run": ("running_gravel.mp3", -16),
    "runs": ("running_gravel.mp3", -16),
    "running": ("running_gravel.mp3", -16),
    "drag": ("running_gravel.mp3", -16),
    "dragged": ("running_gravel.mp3", -14),
    "slide": ("chair_scrape.mp3", -18),
    "slides": ("chair_scrape.mp3", -18),
    "screech": ("raccoon_screech.mp3", -14),
    "screeching": ("raccoon_screech.mp3", -14),
    "wrestle": ("raccoon_sounds.mp3", -12),
    "swatting": ("raccoon_sounds.mp3", -13),
    "fighting": ("raccoon_sounds.mp3", -12),
    "chaos": ("raccoon_sounds.mp3", -13),
    "flop": ("fish_flop.mp3", -16),
    "flops": ("fish_flop.mp3", -16),
    "flopping": ("fish_flop.mp3", -16),
    "wobble": ("fish_flop.mp3", -22),
    "wobbling": ("fish_flop.mp3", -22),
    "stumble": ("heavy_thud.mp3", -20),
    "stumbles": ("heavy_thud.mp3", -20),
    "throws": ("briefcase_drop.mp3", -16),
    "throw": ("briefcase_drop.mp3", -16),
    "rips": ("fabric_rip.mp3", -16),
    "rip": ("fabric_rip.mp3", -16),
    "kicks": ("heavy_thud.mp3", -18),
    "door": ("door_creak.mp3", -18),
    "yell": ("man_yell.mp3", -14),
    "yelling": ("man_yell.mp3", -14),
    "grunt": ("man_grunt.mp3", -16),
    "lurches": ("man_grunt.mp3", -16),
    "high-five": ("high_five.mp3", -16),
    "laughter": ("laughter.mp3", -16),
    "laughing": ("laughter.mp3", -16),
    "murmur": ("crowd_murmur.mp3", -18),
    "staff": ("crowd_murmur.mp3", -20),
    "book": ("page_turn.mp3", -22),
    "page": ("page_turn.mp3", -22),
    "phone": ("poker_chips.mp3", -24),
    "typing": ("poker_chips.mp3", -24),
    "exhale": ("wind_gust.mp3", -18),
    "smoke": ("wind_gust.mp3", -20),
    "wing": ("wind_gust.mp3", -14),
    "wings": ("wind_gust.mp3", -14),
    "roar": ("dragon_roar.mp3", -12),
    "growl": ("dragon_roar.mp3", -14),
    "hover": ("ufo_hum.mp3", -10),
    "hovers": ("ufo_hum.mp3", -10),
    "beam": ("ufo_hum.mp3", -12),
    "ufo": ("ufo_hum.mp3", -10),
    "saucer": ("ufo_hum.mp3", -10),
    "abduct": ("ufo_zip.mp3", -10),
    "abducts": ("ufo_zip.mp3", -10),
    "zip": ("ufo_zip.mp3", -12),
    "zips": ("ufo_zip.mp3", -12),
    "panic": ("raccoon_sounds.mp3", -12),
    "panicking": ("raccoon_sounds.mp3", -12),
    "chittering": ("raccoon_sounds.mp3", -14),
    "snarl": ("raccoon_screech.mp3", -14),
    "snarls": ("raccoon_screech.mp3", -14),
    "flailing": ("fabric_rip.mp3", -18),
    "float": ("wind_gust.mp3", -20),
    "floats": ("wind_gust.mp3", -20),
    "reel": ("fishing_reel.mp3", -14),
    "rod": ("fishing_reel.mp3", -16),
    "fishing line": ("fishing_reel.mp3", -14),
    "creak": ("door_creak.mp3", -18),
    "water": ("lake_water.mp3", -20),
    "lake": ("lake_water.mp3", -22),
    "clap": ("clap_single.mp3", -14),
    "claps": ("clap_single.mp3", -14),
    "clapping": ("clap_single.mp3", -12),
    "whistle": ("whistle_blow.mp3", -12),
    "blowing whistle": ("whistle_blow.mp3", -10),
    "scream": ("man_yell.mp3", -12),
    "screams": ("man_yell.mp3", -12),
    "screaming": ("man_yell.mp3", -12),
    "shout": ("man_yell.mp3", -14),
    "shouts": ("man_yell.mp3", -14),
    "shouting": ("man_yell.mp3", -14),
    "encourage": ("man_yell.mp3", -18),
    "encouraging": ("man_yell.mp3", -18),
    "gasp": ("gasp.mp3", -14),
    "gasps": ("gasp.mp3", -14),
    "startled": ("gasp.mp3", -14),
    "scared": ("gasp.mp3", -14),
    "jumps": ("heavy_thud.mp3", -14),
    "jump": ("heavy_thud.mp3", -14),
    "frog": ("frog_croak.mp3", -16),
    "croak": ("frog_croak.mp3", -16),
    "swing": ("golf_swing.mp3", -14),
    "swings": ("golf_swing.mp3", -14),
    "drives": ("golf_swing.mp3", -14),
    "guitar": ("guitar_strum.mp3", -16),
    "strum": ("guitar_strum.mp3", -14),
    "strumming": ("guitar_strum.mp3", -14),
    "cooking": ("chair_scrape.mp3", -20),
    "grill": ("chair_scrape.mp3", -20),
    "tongs": ("poker_chips.mp3", -20),
    "cast": ("fishing_reel.mp3", -14),
    "casts": ("fishing_reel.mp3", -14),
    "catches": ("splash_large.mp3", -14),
    "caught": ("splash_large.mp3", -16),
    "trip": ("heavy_thud.mp3", -14),
    "trips": ("heavy_thud.mp3", -14),
    "collapse": ("heavy_thud.mp3", -14),
    "collapses": ("heavy_thud.mp3", -14),
    "bump": ("heavy_thud.mp3", -16),
    "bumps": ("heavy_thud.mp3", -16),
    "duck": ("man_grunt.mp3", -18),
    "ducks": ("man_grunt.mp3", -18),
    "ducking": ("man_grunt.mp3", -18),
    "nod": ("wind_gust.mp3", -24),
    "nods": ("wind_gust.mp3", -24),
    "points": ("wind_gust.mp3", -24),
    "pointing": ("wind_gust.mp3", -24),
    "scatter": ("running_gravel.mp3", -14),
    "scatters": ("running_gravel.mp3", -14),
    "scramble": ("running_gravel.mp3", -14),
    "scrambles": ("running_gravel.mp3", -14),
    "flinch": ("gasp.mp3", -16),
    "flinches": ("gasp.mp3", -16),
    "recoils": ("gasp.mp3", -16),
    "shrug": ("wind_gust.mp3", -24),
    "shrugs": ("wind_gust.mp3", -24),
    "snap": ("card_slam.mp3", -14),
    "snaps": ("card_slam.mp3", -14),
    "kick": ("heavy_thud.mp3", -16),
    "sip": ("lake_water.mp3", -22),
    "sips": ("lake_water.mp3", -22),
    "falls": ("heavy_thud.mp3", -14),
    "fell": ("heavy_thud.mp3", -14),
    "drops": ("briefcase_drop.mp3", -16),
    "gestures": ("wind_gust.mp3", -24),
    "gesturing": ("wind_gust.mp3", -24),
}

# Volume tiers for reference
VOL_LOUD = -12    # big impacts, climax sounds
VOL_MEDIUM = -16  # standard action sounds
VOL_QUIET = -20   # subtle/background sounds
VOL_BARELY = -24  # barely audible texture


# ──────────────────────────────────────────────────────────────
# AUDIO SPECS — per-idea sound design (hand-tuned override auto)
# Each layer: file, start_sec, volume_db, in_scene (phone mic filter)
# in_scene=True gets low-pass filter to simulate phone mic recording
# ──────────────────────────────────────────────────────────────
AUDIO_SPECS = {
    "cctv_raccoon_poker": {
        "layers": [
            {"file": "ambient_night.mp3", "start": 0.0, "volume_db": -8, "in_scene": True, "loop": True},
            {"file": "news_sting_short.mp3", "start": 0.0, "volume_db": -10, "in_scene": False},
            {"file": "card_slam.mp3", "start": 5.0, "volume_db": -22, "in_scene": True},
            {"file": "poker_chips.mp3", "start": 5.2, "volume_db": -24, "in_scene": True},
            {"file": "raccoon_screech.mp3", "start": 8.0, "volume_db": -14, "in_scene": True},
            {"file": "table_crash.mp3", "start": 11.0, "volume_db": -16, "in_scene": True},
            {"file": "raccoon_sounds.mp3", "start": 12.0, "volume_db": -12, "in_scene": True},
            {"file": "raccoon_sounds.mp3", "start": 13.5, "volume_db": -13, "in_scene": True},
        ],
    },
    "cctv_ufo_raccoons": {
        "layers": [
            {"file": "ambient_night.mp3", "start": 0.0, "volume_db": -8, "in_scene": True, "loop": True},
            {"file": "ufo_hum.mp3", "start": 0.0, "volume_db": -10, "in_scene": True, "loop": True},
            {"file": "raccoon_sounds.mp3", "start": 2.0, "volume_db": -14, "in_scene": True},
            {"file": "raccoon_screech.mp3", "start": 4.0, "volume_db": -12, "in_scene": True},
            {"file": "wind_gust.mp3", "start": 5.5, "volume_db": -14, "in_scene": True},
            {"file": "raccoon_screech.mp3", "start": 7.0, "volume_db": -11, "in_scene": True},
            {"file": "raccoon_sounds.mp3", "start": 8.5, "volume_db": -12, "in_scene": True},
            {"file": "ufo_zip.mp3", "start": 10.0, "volume_db": -8, "in_scene": True},
            {"file": "raccoon_screech.mp3", "start": 10.5, "volume_db": -10, "in_scene": True},
            {"file": "raccoon_sounds.mp3", "start": 12.0, "volume_db": -12, "in_scene": True},
        ],
    },
}


# ──────────────────────────────────────────────────────────────
# VIDEO MOTION ANALYZER — extracts exact impact timestamps from
# the actual generated video. No guessing, no estimates.
#
# Extracts frames every 0.25s, computes frame-to-frame pixel
# difference, finds spikes = impacts/action beats. Returns
# precise timestamps ranked by intensity.
# ──────────────────────────────────────────────────────────────

PLATE_USAGE_FILE = DATA_DIR / "plate_usage.json"


# ──────────────────────────────────────────────────────────────
# SCENE CONTEXT ENRICHMENT — forces physical/logical realism
#
# Every prompt sent to Kling gets wrapped with grounding rules.
# This prevents: objects appearing from nowhere, things in wrong
# locations (fish on dry land with no explanation), broken physics,
# environment inconsistencies.
# ──────────────────────────────────────────────────────────────

SCENE_CONTEXT_PREFIX = (
    "CRITICAL REALISM RULES — follow these exactly:\n"
    "1. Every object must already exist in the starting frame OR enter from off-screen "
    "with a visible, physically logical entrance path (walking, swimming, flying in). "
    "Nothing materializes from thin air.\n"
    "2. Animals and objects must be in environments that make physical sense. "
    "Fish must be in or near water unless they visibly flopped out of it. "
    "A bass on dry land must show HOW it got there (jumping from lake, flopping from bucket). "
    "No animal appears on a surface where it could not logically be.\n"
    "3. All motion must have cause and effect. If something moves, show what pushed/pulled it. "
    "If something falls, gravity pulled it. If something flies, it has wings or was thrown.\n"
    "4. The environment in the starting frame is the GROUND TRUTH. Do not change the buildings, "
    "terrain, surfaces, trees, or structures. Only add motion and characters that interact "
    "with the existing environment.\n"
    "5. Maintain consistent lighting, weather, and time of day from the starting frame "
    "throughout the entire video. No sudden shifts.\n"
    "6. Single continuous shot, no cuts, no jump edits.\n\n"
    "SCENE:\n"
)

SURFACE_CONTEXT = {
    "road_grass": "gravel road with grass shoulders and dirt patches, rural East Texas property",
    "dock": "wooden boat dock extending over lake water, boats tied up nearby",
    "concrete": "poured concrete pad in front of metal-sided fishing cabin",
    "deck": "raised wooden deck with picnic tables under a covered pavilion area",
    "grass": "mowed grass clearing with a metal boat shed and scattered equipment",
    "lake": "calm lake water surface with cypress trees along the shoreline",
}

ANIMAL_REALITY = {
    "bass": "must be in water, jumping FROM water, flopping on a dock they jumped onto from the water, or being held by a fisherman who caught them. Never on dry grass or road with no water nearby.",
    "fish": "same rules as bass — aquatic animals need water context",
    "raccoon": "can be anywhere on the property — they're land animals that climb, open things, and cause mischief",
    "deer": "can walk through the property naturally — they live in East Texas woods",
    "armadillo": "ground-level, can be on roads, grass, near cabins — native to East Texas",
    "squirrel": "in trees, on railings, on decks — anywhere a squirrel would actually be",
    "frog": "near water, in grass, on wet surfaces — not on dry concrete in direct sun",
    "dragon": "fantasy creature — no reality rules, but it must still interact with the real environment physically (land on real surfaces, knock over real objects)",
    "ufo": "fantasy element — must still interact with physics (tractor beam has visible light cone, lifted objects rise gradually not teleport, water/dust displaced by thrust)",
}


# ──────────────────────────────────────────────────────────────
# THE ROWDY RACCOONS — locked visual identity
#
# These three raccoons must look IDENTICAL across every video.
# Their appearance is defined here once and injected into any
# prompt that includes raccoons. This is the canonical look
# from the poker video.
# ──────────────────────────────────────────────────────────────

RACCOON_IDENTITY = (
    "CHARACTER LOCK — THE ROWDY RACCOONS (must look the same in every video):\n"
    "There are exactly THREE raccoons. They are always three distinct, separate animals — "
    "they NEVER merge, overlap, blend into each other, or become one shape. "
    "Each raccoon is individually visible at all times.\n"
    "ALL THREE ARE THE SAME BODY SIZE — same height, same weight, same chunky build. "
    "None is smaller. None is bigger. None is a baby. They are the same age and species. "
    "The ONLY differences are fur shade, mask markings, tail, and behavior:\n"
    "Raccoon 1 (LIGHTER FUR): Slightly lighter grey-brown coat than the others. The leader. "
    "Moves with confidence, stands taller on hind legs. Ear has a small notch on the left side.\n"
    "Raccoon 2 (DARK MASK): Darker, more prominent black mask markings around the eyes than the "
    "other two — almost like wearing a bandit mask. Same body size as the others. The schemer. "
    "Always looking sideways, shifty body language.\n"
    "Raccoon 3 (BUSHY TAIL): Bushiest, most dramatically striped tail of the three — "
    "tail is almost comically oversized. Same body size as the others. The hothead. Quick, "
    "aggressive movements, first to flip a table or throw something.\n"
    "All three have standard raccoon coloring (grey-brown fur, black mask, ringed tail) but "
    "these distinguishing features make each one recognizable. They are wild raccoons — "
    "no cartoon proportions, realistic animal anatomy and movement.\n"
)

# ══════════════════════════════════════════════════════════════
# GROK GUARDRAILS — UNIVERSAL PRINCIPLES
# Every lesson learned from any single image gets hardcoded here
# so it applies to ALL future images automatically. These are not
# raccoon rules — they are image generation rules.
#
# PRINCIPLE 1: WHAT YOU DON'T BAN WILL APPEAR
#   Grok adds props, cameras, text, and accessories by default.
#   Every prompt must explicitly ban everything that doesn't belong.
#
# PRINCIPLE 2: FIRST DESCRIBED = DOMINANT
#   Grok makes the first-described element visually dominant.
#   Always describe the most important element first.
#
# PRINCIPLE 3: GROUPS MUST BE SAME-SIZED UNLESS TOLD OTHERWISE
#   When multiple subjects of the same type appear, Grok makes
#   them wildly different sizes. Must enforce uniform sizing.
#
# PRINCIPLE 4: SIZE WORDS ARE TAKEN LITERALLY
#   "small", "tiny", "biggest", "smallest" cause size chaos.
#   Distinguish characters by COLOR and MARKINGS, never body size.
#
# PRINCIPLE 5: CAMERA TYPE = PERSPECTIVE, NOT PROP
#   "CCTV format" means shot FROM a security camera angle.
#   Grok adds a physical CCTV camera to the scene. Must ban it.
#
# PRINCIPLE 6: CROSS-VIDEO CONTAMINATION
#   Grok bleeds props from previously seen images (poker chips
#   on raccoons in non-poker scenes). Must ban explicitly.
#
# PRINCIPLE 7: SKY OBJECTS DEFAULT TO GROUND LEVEL
#   UFOs, helicopters, portals — Grok places them on the ground
#   unless you say "UPPER THIRD of frame, ABOVE roofline" with
#   frame-fraction sizing (not just "large" or "20 feet wide").
#
# PRINCIPLE 8: BACKGROUND IS SACRED
#   The plate photo is ground truth. Nothing in it changes.
# ══════════════════════════════════════════════════════════════

# ── P1: BAN EVERYTHING THAT DOESN'T BELONG ──────────────────

GROK_CONTAMINATION_BANS = (
    "Do NOT add ANY of the following items or accessories to the scene: "
    "poker chips, playing cards, card tables, gambling items, gold chains, "
    "sunglasses, visors, hats, costumes, jerseys, sports equipment, "
    "BBQ grills (unless this IS the BBQ video), chef hats, aprons, "
    "luggage, briefcases, ties, clipboards, microphones, news desks, "
    "trophies, medals, crowns, buses, RVs, motor coaches, tour buses, "
    "school buses, vans, or large vehicles of any kind. "
    "Animals are PLAIN WILD ANIMALS with no props or accessories "
    "unless this specific video calls for them. "
    "People wear only what is explicitly described — no extra clothing, "
    "accessories, or items."
)

GROK_VEHICLE_BAN = (
    "VEHICLE BAN — CRITICAL: Do NOT add any buses, RVs, motor coaches, "
    "tour buses, vans, or large vehicles. There are NO buses at this property. "
    "If you see a bus in your output, you have made an error — remove it."
)

GROK_NEGATIVE_INSTRUCTIONS = (
    "Do NOT add any text, labels, watermarks, timestamps, overlay graphics, "
    "or signs to the image. Do NOT add a physical CCTV camera, security camera, "
    "camera pole, camera mount, or any camera equipment as a prop in the scene. "
    "The camera perspective is the VIEWER'S point of view — it is NOT a physical "
    "object in the scene. Do NOT add any props, objects, animals, or people not "
    "explicitly described in this prompt. If it is not mentioned, it should not exist."
)

# ── P5: CAMERA TYPE = PERSPECTIVE, NOT PROP ──────────────────

GROK_FORMAT_RULES = {
    "cctv": (
        "CAMERA PERSPECTIVE: This is shot FROM a wide-angle security camera mounted "
        "high on a wall, looking slightly down. The viewer IS the camera. "
        "Do NOT place a CCTV camera, pole, sign, label, or any camera equipment "
        "as a physical object visible in the image. There is NO camera in the scene."
    ),
    "news": (
        "CAMERA PERSPECTIVE: This looks like phone camera footage — slightly off-angle, "
        "natural framing, like someone whipped out their phone to record. "
        "Do NOT add a news desk, microphone, reporter, teleprompter, or any "
        "broadcast equipment as a physical object in the scene."
    ),
    "impossible": (
        "CAMERA PERSPECTIVE: Cinematic quality, clean framing, slightly surreal lighting. "
        "Do NOT add any camera equipment as a physical object in the scene."
    ),
}

# ── P3 + P4: SUBJECT GROUP RULES ────────────────────────────
# These apply to ANY group of same-type subjects, not just raccoons.

GROK_SUBJECT_GROUPS = {
    "raccoon": {
        "keywords": ["raccoon", "rowdy"],
        "count": 3,
        "count_lock": (
            "There are EXACTLY THREE raccoons in this scene — no more, no fewer. "
            "Count them: one, two, three. Do NOT add a fourth raccoon. "
            "Do NOT add a baby raccoon. Do NOT add any extra animals. "
            "If you see 4, remove one. THREE. EXACTLY THREE."
        ),
        "size_lock": (
            "ALL THREE RACCOONS ARE THE SAME SIZE. They are all full-grown adult raccoons "
            "with the same chunky body proportions — same height, same weight, same build. "
            "None is smaller. None is bigger. None is a baby. They are identical in body size. "
            "The ONLY differences between them are fur shade, mask markings, and tail bushiness — "
            "NOT body size. If one raccoon looks smaller or bigger than the others, fix it."
        ),
        "identity_lock": (
            "Each raccoon MUST be visually distinct but THE SAME BODY SIZE:\n"
            "Raccoon 1: Slightly lighter grey-brown fur, small notch on left ear.\n"
            "Raccoon 2: Darker, more prominent black mask markings around the eyes.\n"
            "Raccoon 3: Bushiest, most dramatically striped tail — tail is oversized.\n"
            "ALL THREE have the same chunky body, same height, same weight. "
            "They look like siblings — same species, same age, same build. "
            "Realistic wild raccoons, no cartoon proportions."
        ),
    },
    "deer": {
        "keywords": ["deer", "buck", "doe"],
        "count": None,
        "count_lock": None,
        "size_lock": (
            "All deer in this scene are the SAME SIZE — full-grown adult deer, "
            "same height, same build. None is a fawn. None is smaller or bigger "
            "than the others. Distinguish them by antler size or coat shade only, "
            "NOT body size."
        ),
        "identity_lock": None,
    },
    "bear": {
        "keywords": ["bear"],
        "count": None,
        "count_lock": None,
        "size_lock": (
            "All bears in this scene are the SAME SIZE — full-grown adult bears, "
            "same height, same build. None is a cub. None is smaller or bigger "
            "than the others. Realistic proportions."
        ),
        "identity_lock": None,
    },
    "person": {
        "keywords": ["people", "persons", "guys", "men", "women", "group of"],
        "count": None,
        "count_lock": None,
        "size_lock": (
            "All people in this scene are the SAME HEIGHT unless explicitly described "
            "otherwise. Standard adult proportions. No one is randomly taller or shorter."
        ),
        "identity_lock": None,
    },
    "fish": {
        "keywords": ["fish", "bass", "catfish"],
        "count": None,
        "count_lock": None,
        "size_lock": (
            "All fish in this scene are the SAME SIZE — full-grown adult fish, "
            "same length. None is a fingerling. None is randomly bigger or smaller."
        ),
        "identity_lock": None,
    },
    "armadillo": {
        "keywords": ["armadillo"],
        "count": None,
        "count_lock": None,
        "size_lock": (
            "All armadillos in this scene are the SAME SIZE — full-grown adults, "
            "same body proportions. None is smaller or bigger than the others."
        ),
        "identity_lock": None,
    },
}

# Universal size uniformity — injected for ANY group of 2+ same-type subjects
GROK_UNIVERSAL_SIZE_RULE = (
    "SUBJECT SIZE RULE: When multiple subjects of the same type appear in this image, "
    "they MUST all be the SAME BODY SIZE — same height, same proportions, same build. "
    "Distinguish them by COLOR, MARKINGS, POSE, or POSITION — never by making one "
    "bigger or smaller than the others. If they are described as the same type of "
    "animal or person, they are the same size."
)

# Universal realism — injected on every prompt
GROK_UNIVERSAL_REALISM = (
    "REALISM: Shadows match existing light. Feet/paws touch ground (no floating). "
    "Scale subjects relative to buildings. Sky objects ABOVE roofline. "
    "Lighting on added subjects matches the plate exactly.\n"
    "OBJECT SCALE: Every object (grills, tables, chairs, coolers, tackle boxes, trucks) "
    "must be REAL HUMAN SIZE. Animals are small compared to human objects — a raccoon "
    "is knee-height next to a full-size grill, NOT the same size as it. Never shrink "
    "objects to match animal size. The animals live in a HUMAN-SCALE world.\n"
    "OBJECT PLACEMENT: Grills, tables, and furniture go on CONCRETE or DECK surfaces, "
    "never randomly on grass. Vehicles go on driveways or gravel roads, never on lawn. "
    "Place objects where they would realistically be at a rural cabin property. "
    "Do NOT add vehicles (buses, RVs, trucks) unless explicitly requested."
)

# ── P2 + P7: HERO ELEMENT PROPORTION ENFORCEMENT ────────────

GROK_HERO_ELEMENTS = {
    "sky": {
        "keywords": ["ufo", "flying saucer", "spaceship", "spacecraft", "meteor",
                     "asteroid", "helicopter", "plane", "blimp", "drone swarm",
                     "hot air balloon", "portal"],
        "proportion": (
            "SIZE AND POSITION — MOST IMPORTANT:\n"
            "The {element} is the DOMINANT element — at least 30% of the image. "
            "UPPER THIRD of frame, ABOVE roofline, at treetop height or higher. "
            "BIGGER than every building, tree, and animal. NOT small, NOT a toy."
        ),
    },
    "large_creature": {
        "keywords": ["bigfoot", "sasquatch", "monster", "dinosaur", "giant",
                     "godzilla", "king kong"],
        "proportion": (
            "SIZE AND POSITION — THIS IS THE MOST IMPORTANT INSTRUCTION:\n"
            "The {element} is MASSIVE — taller than the cabin doors, at least 8 feet tall. "
            "It MUST be the tallest non-building object in the scene. "
            "It takes up at least 25% of the total image area. "
            "Any animals nearby are TINY compared to it."
        ),
    },
    "tall_person": {
        "keywords": ["shaq", "7-foot", "7 foot", "very tall man", "giant person"],
        "proportion": (
            "SIZE AND POSITION — THIS IS THE MOST IMPORTANT INSTRUCTION:\n"
            "This person is extremely tall — their head is ABOVE the door frame. "
            "They must be clearly taller than the doorway. The door reaches their chest. "
            "Their shoulders are wider than the doorframe."
        ),
    },
    "vehicle": {
        "keywords": ["truck", "bulldozer", "tank", "car", "tractor", "ambulance",
                     "fire truck", "bus"],
        "proportion": (
            "SIZE AND POSITION — THIS IS THE MOST IMPORTANT INSTRUCTION:\n"
            "The {element} is a full-sized real vehicle — as wide as a cabin, "
            "taller than a person. It takes up at least 20% of the image. "
            "It is NOT a toy. It is NOT miniature."
        ),
    },
}

GROK_ANIMAL_SUBORDINATION = (
    "The animals are SMALL in comparison — they are realistic wild animal size, "
    "about knee-height on an adult human. They should NOT dominate the frame. "
    "The {hero} is the star of this image, not the animals."
)


# ── P9-P11: UNIVERSAL KLING VIDEO MOTION RULES ───────────────
# These get injected into _enrich_prompt() for every video generation.

KLING_MOTION_RULES = (
    "MOTION RULES — APPLY TO EVERY VIDEO:\n"
    "- DEPARTURES ARE FAST: When anything exits the frame — abducted, flies away, "
    "drives off, runs away, gets pulled, launched, ejected — it happens SUDDENLY and "
    "QUICKLY. No slow drifting. No gentle floating. A UFO grabs and ZIPS away in 1-2 "
    "seconds. A car PEELS OUT. A creature BOLTS. The audience should barely have time "
    "to process it before it's gone.\n"
    "- BYSTANDERS MUST REACT: If some subjects witness an event happening to another "
    "subject, the bystanders show VISIBLE emotional and physical reactions throughout "
    "the entire video. They do NOT stand motionless watching. They panic, flee, screech, "
    "cower, scramble, fight each other, stumble backwards, hide behind objects. Their "
    "reactions should ESCALATE as the event gets more dramatic.\n"
    "- NO FROZEN SUBJECTS: Every subject in every frame must be DOING something. No "
    "statues. No subjects standing perfectly still. Even waiting subjects shift weight, "
    "look around, twitch ears, swish tails, fidget."
)

# P15: ACTION SPECIFICITY — Kling defaults to generic "animals playing around"
# when the prompt doesn't hammer the EXACT physical actions. Every subject must
# have a specific described body position and motion, not a vague activity.
KLING_ACTION_SPECIFICITY = (
    "ACTION SPECIFICITY — CRITICAL:\n"
    "- Every subject must perform the EXACT physical action described in the prompt. "
    "Do NOT substitute generic playing, walking, or standing around.\n"
    "- If the prompt says 'doing push-ups', subjects must be in push-up position with "
    "arms bending and extending. If it says 'coaching', the coach must be standing upright, "
    "pointing, gesturing, demonstrating — NOT crouching to pet or play.\n"
    "- Subjects must maintain their ROLE throughout the video. A coach COACHES (stands, "
    "points, blows whistle, demonstrates). Athletes TRAIN (push-ups, running, drills). "
    "A chef COOKS. A security guard PATROLS. Never collapse distinct roles into generic "
    "interaction.\n"
    "- The PRIMARY ACTION described in the prompt is the MOST IMPORTANT element. "
    "Kling must depict THIS action, not a looser interpretation of the scene concept."
)

HEADLINE_CHARACTER_NAMES = [
    (r'\braccoons?\b', "the Rowdy Raccoons"),
]

# ── P17: CELEBRITY PROP CONTAMINATION GUARD ─────────────────
# Grok's image model associates celebrities with their iconic props/environments.
# Saying "Deion Sanders" triggers a coach bus. "LeBron" triggers a basketball court.
# Each celebrity gets explicit counter-bans for their associated contamination items.
CELEBRITY_PROP_BANS = {
    "deion sanders": "Do NOT add ANY bus (school bus, coach bus, team bus, tour bus, yellow bus), RV, large vehicle, football field, stadium, sideline, football equipment, goalpost, or any vehicle larger than a pickup truck.",
    "deion": "Do NOT add ANY bus (school bus, coach bus, team bus, tour bus, yellow bus), RV, large vehicle, football field, stadium, sideline, football equipment, goalpost, or any vehicle larger than a pickup truck.",
    "coach prime": "Do NOT add ANY bus (school bus, coach bus, team bus, tour bus, yellow bus), RV, large vehicle, football field, stadium, sideline, football equipment, goalpost, or any vehicle larger than a pickup truck.",
    "lebron james": "Do NOT add a basketball court, basketball hoop, basketball, arena, stadium, scoreboard, bench, or sports arena equipment.",
    "lebron": "Do NOT add a basketball court, basketball hoop, basketball, arena, stadium, scoreboard, bench, or sports arena equipment.",
    "shaq": "Do NOT add a basketball court, basketball hoop, basketball, arena, stadium, fast food restaurant, or sports arena equipment.",
    "shaquille": "Do NOT add a basketball court, basketball hoop, basketball, arena, stadium, fast food restaurant, or sports arena equipment.",
    "kevin hart": "Do NOT add a comedy stage, microphone stand, spotlight, audience, theater, red carpet, or movie set equipment.",
    "gordon ramsay": "Do NOT add a restaurant kitchen, stove, oven, commercial kitchen equipment, white chef coat, or restaurant dining room.",
    "guy fieri": "Do NOT add a red convertible, Camaro, sports car, restaurant interior, diner, or Flavor Town signage.",
    "snoop dogg": "Do NOT add a recording studio, concert stage, lowrider, sports car, or music equipment beyond what's described.",
    "snoop": "Do NOT add a recording studio, concert stage, lowrider, sports car, or music equipment beyond what's described.",
    "post malone": "Do NOT add a recording studio, concert stage, music equipment, or nightclub setting.",
    "joe rogan": "Do NOT add a podcast studio, podcast desk, professional microphones, soundproofing panels, or studio lighting beyond what's described.",
    "tiger woods": "Do NOT add a golf course, golf green, sand trap, golf cart, caddy, or country club.",
    "taylor swift": "Do NOT add a concert stage, arena, tour bus, crowd, microphone stand, or music equipment beyond what's described.",
    "trump": "Do NOT add a podium, American flags, Secret Service agents, suit-wearing entourage, limousine, or political rally equipment.",
    "morgan freeman": "Do NOT add a movie set, camera equipment, director's chair, film crew, or studio lighting.",
    "matthew mcconaughey": "Do NOT add a luxury car, Lincoln, movie set, or Hollywood equipment.",
    "mcconaughey": "Do NOT add a luxury car, Lincoln, movie set, or Hollywood equipment.",
    "dwayne johnson": "Do NOT add a wrestling ring, gym equipment, movie set, or action movie props.",
    "the rock": "Do NOT add a wrestling ring, gym equipment, movie set, or action movie props.",
    "chuck norris": "Do NOT add a martial arts dojo, karate equipment, movie set, or action movie props.",
    "mahomes": "Do NOT add a football field, stadium, goalpost, football, sports arena, or sideline equipment.",
    "patrick mahomes": "Do NOT add a football field, stadium, goalpost, football, sports arena, or sideline equipment.",
    "travis kelce": "Do NOT add a football field, stadium, goalpost, football, sports arena, or sideline equipment.",
    "dj khaled": "Do NOT add a recording studio, DJ equipment, turntables, concert stage, or jet ski.",
    "willie nelson": "Do NOT add a tour bus, concert stage, band equipment, or music venue.",
    "bear grylls": "Do NOT add a helicopter, parachute, jungle, extreme terrain, or survival show camera crew.",
    "bill murray": "Do NOT add a movie set, golf course, comedy club, or film equipment.",
    "mark cuban": "Do NOT add an office building, TV studio, Shark Tank set, or corporate boardroom.",
}


def _detect_celebrity_bans(text):
    """Scan prompt text for celebrity names and return their prop ban strings."""
    text_lower = text.lower()
    bans = []
    seen = set()
    for name, ban in CELEBRITY_PROP_BANS.items():
        if name in text_lower and ban not in seen:
            bans.append(ban)
            seen.add(ban)
    return bans

# ──────────────────────────────────────────────────────────────
# P16: Sign compositing — per-plate positions for "Scenic 515 Cabins" sign
# (x_px, y_bottom_px, scale_factor) on 1920x1080 plates
# y_bottom_px = where the pole touches the ground
# scale_factor = sign width as proportion of plate width
# ──────────────────────────────────────────────────────────────
SIGN_FILE = DATA_DIR / "media" / "sign_final.png"
PLATES_SIGNED_DIR = DATA_DIR / "media" / "plates_signed"
GROK_READY_DIR = PLATES_DIR / "grok_ready"

# Map grok_ready filenames → output plate names + sign position (x, y_bottom, sign_pixel_width[, pole_extend])
SIGN_POSITIONS = {
    "01_gravel_road_with_cabins.jpg":      ("plate_0001", 560, 650, 140),
    "05_boat_storage_area.jpg":            ("plate_0005", 380, 680, 130),
    "10_cabin_parking_entrance.jpg":       ("plate_0010", 400, 650, 140),
    "70_concrete_patio_firepit.jpg":       ("plate_0070", 380, 500, 130),
    "80_outdoor_area_between_cabins.jpg":  ("plate_0080", 50, 680, 120),
    "90_cabin_exterior_wide.jpg":          ("plate_0090", 150, 520, 110),
    "102_grass_lawn_between_cabins.jpg":   ("plate_0102", 300, 620, 192),
    "110_paved_road_utility_pole.jpg":     ("plate_0110", 600, 845, 120),
}


def _compose_sign_on_plate(plate_id=None):
    """Composite sign_final.png onto cleaned grok_ready plates → plates_signed/."""
    from PIL import Image, ImageDraw

    if not SIGN_FILE.exists():
        print(f"ERROR: {SIGN_FILE} not found")
        return
    sign = Image.open(SIGN_FILE)
    sign_w, sign_h = sign.size
    PLATES_SIGNED_DIR.mkdir(parents=True, exist_ok=True)

    for src_name, pos_tuple in SIGN_POSITIONS.items():
        out_id, x, y_bottom, target_w = pos_tuple[:4]
        pole_extend = pos_tuple[4] if len(pos_tuple) > 4 else 0
        railing_bands = pos_tuple[5] if len(pos_tuple) > 5 else None
        if plate_id and out_id != plate_id:
            continue
        src = GROK_READY_DIR / src_name
        if not src.exists():
            print(f"  SKIP {out_id}: {src_name} not found")
            continue
        plate = Image.open(src).convert("RGBA")
        new_w = target_w
        new_h = int(new_w * sign_h / sign_w)
        sign_scaled = sign.resize((new_w, new_h), Image.LANCZOS)

        if pole_extend > 0:
            sign_face_crop = sign.crop((0, 0, sign_w, 440))
            face_h = int(new_w * 440 / sign_w)
            sign_face = sign_face_crop.resize((new_w, face_h), Image.LANCZOS)
            total_h = face_h + pole_extend
            extended = Image.new("RGBA", (new_w, total_h), (0, 0, 0, 0))
            extended.paste(sign_face, (0, 0), sign_face)
            pole_w = max(6, new_w // 16)
            pole_x = (new_w - pole_w) // 2
            draw = ImageDraw.Draw(extended)
            draw.rectangle([pole_x, face_h, pole_x + pole_w, total_h], fill=(30, 30, 30, 255))
            sign_scaled = extended
            new_h = total_h

        y_top = y_bottom - new_h
        if y_top < 0:
            y_top = 0
        original = plate.copy() if railing_bands else None
        plate.paste(sign_scaled, (x, y_top), sign_scaled)

        if railing_bands and pole_extend > 0:
            pole_px = x + (new_w - pole_w) // 2
            orig_px = original.load()
            comp_px = plate.load()
            for ry_start, ry_end in railing_bands:
                for py in range(ry_start, ry_end):
                    for px in range(pole_px - 3, pole_px + pole_w + 3):
                        if 0 <= px < plate.width and 0 <= py < plate.height:
                            comp_px[px, py] = orig_px[px, py]
        out_path = PLATES_SIGNED_DIR / f"{out_id}.jpg"
        plate.convert("RGB").save(out_path, "JPEG", quality=95)
        print(f"  {out_id}: sign at ({x},{y_top}) size {new_w}x{new_h}" + (f" (pole +{pole_extend}px)" if pole_extend else ""))
    print(f"Done. Signed plates in {PLATES_SIGNED_DIR}")


def _fix_headline_character_names(headline):
    """Auto-fix headlines to use established character names."""
    import re
    result = headline
    for pattern_str, named in HEADLINE_CHARACTER_NAMES:
        pattern = re.compile(
            r'(?<![Rr]owdy\s)' + pattern_str,
            re.IGNORECASE
        )
        if pattern.search(result):
            result = pattern.sub(named, result, count=1)
    return result


def _clean_headline(headline):
    """P14: Strip em dashes, explanations, and editorializing from headlines.
    Headlines must be clean factual statements — no '—', no 'one keeps quitting',
    no commentary. Just: WHO + WHAT + WHERE (515 Scenic Cabins on Lake Fork)."""
    import re
    result = headline.strip()
    result = re.sub(r'\s*[—–-]{1,3}\s*.+$', '', result)
    result = re.sub(r',\s*(one|he|she|they|it|all|both|the)\b.*$', '', result, flags=re.IGNORECASE)
    if '515' not in result:
        result = result.rstrip('.!') + ' at 515 Scenic Cabins on Lake Fork'
    return result.strip()


# ── P12: WEAK VERB AUTO-FIX (Kling needs STRONG action verbs) ──
# Generic verbs produce generic motion. Specific verbs = specific motion.
WEAK_VERB_FIXES = {
    r'\bmoves\b': 'lurches',
    r'\bgoes\b': 'charges',
    r'\bwalks slowly\b': 'creeps',
    r'\bgets up\b': 'scrambles up',
    r'\bfalls down\b': 'crashes down',
    r'\bgoes up\b': 'rockets upward',
    r'\bgoes away\b': 'bolts away',
    r'\bruns away\b': 'bolts',
    r'\blooks at\b': 'locks eyes with',
    r'\bgoes toward\b': 'charges toward',
    r'\bcomes in\b': 'barrels in',
    r'\bcomes out\b': 'bursts out',
    r'\bpicks up\b': 'snatches',
    r'\bputs down\b': 'slams down',
    r'\bgets scared\b': 'freezes in terror',
    r'\bgets angry\b': 'erupts',
    r'\bgets hit\b': 'takes a hit',
}

# P13: PROMPT COMPLEXITY LIMIT — max action beats for 15-second video
KLING_MAX_ACTION_BEATS = 5


def _auto_fix_weak_verbs(scene_prompt):
    """Replace weak/generic verbs with strong specific ones."""
    import re
    result = scene_prompt
    fixes = 0
    for pattern, replacement in WEAK_VERB_FIXES.items():
        new_result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        if new_result != result:
            fixes += 1
        result = new_result
    return result, fixes


def _count_action_beats(scene_prompt):
    """Estimate the number of distinct action beats in a prompt."""
    sentences = [s.strip() for s in scene_prompt.replace('. ', '.|').split('|') if s.strip()]
    skip_phrases = ['important', 'lighting', 'camera', 'keep the same', 'do not change',
                    'single continuous', 'static security', 'filmed on', 'warm evening',
                    'golden hour', 'long shadows', 'always separate', 'never merging']
    action_count = 0
    for s in sentences:
        lower = s.lower()
        if any(sk in lower for sk in skip_phrases):
            continue
        if len(s) > 20:
            action_count += 1
    return action_count


# ── AUTO-DETECTION FUNCTIONS ─────────────────────────────────

def _detect_hero_element(text):
    """Scan prompt text for hero elements. Returns (category, matched_keyword) or (None, None)."""
    text_lower = text.lower()
    for category, info in GROK_HERO_ELEMENTS.items():
        for kw in info["keywords"]:
            if kw in text_lower:
                return category, kw
    return None, None


def _detect_subject_groups(text):
    """Detect which subject groups are present. Returns list of group keys."""
    import re
    text_lower = text.lower()
    found = []
    for group_key, group_info in GROK_SUBJECT_GROUPS.items():
        for kw in group_info["keywords"]:
            if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                found.append(group_key)
                break
    return found


def _build_proportion_block(text, groups=None):
    """Auto-generate proportion enforcement text based on detected hero elements."""
    category, keyword = _detect_hero_element(text)
    if not category:
        return ""

    element_name = keyword
    proportion_text = GROK_HERO_ELEMENTS[category]["proportion"].replace("{element}", element_name)

    result = proportion_text
    has_animals = groups and any(g in ("raccoon", "deer", "bear", "armadillo", "fish") for g in groups)
    if has_animals and category in ("sky", "large_creature", "vehicle"):
        result += "\n\n" + GROK_ANIMAL_SUBORDINATION.replace("{hero}", element_name)

    return result


# ── P4: AUTO-STRIP SIZE-DIFFERENTIAL LANGUAGE ────────────────
# Catches and removes words that cause Grok to make same-type
# subjects different sizes. Works for ANY animal, not just raccoons.

_SIZE_DIFFERENTIAL_WORDS = [
    "smallest build", "smaller build", "stockiest build", "biggest build",
    "largest build", "thinnest build", "fattest build",
]

_ANIMAL_TYPES = [
    "raccoon", "deer", "bear", "armadillo", "fish", "bass", "catfish",
    "dog", "cat", "squirrel", "possum", "coyote", "fox", "rabbit",
    "frog", "turtle", "alligator", "snake",
]

_SIZE_ADJECTIVES = [
    "biggest", "smallest", "tiny", "little", "baby", "huge", "massive",
    "giant", "miniature", "runt", "enormous", "oversized",
]


def _auto_strip_size_language(prompt, groups):
    """Remove size-differential language for any detected subject group."""
    import re as _re

    # Strip universal size-differential build descriptions
    for phrase in _SIZE_DIFFERENTIAL_WORDS:
        prompt = _re.sub(r"(?i)\b" + _re.escape(phrase) + r"\b", "", prompt)

    # Strip "[size adjective] [animal]" but NOT in "Do NOT add a [size] [animal]" negatives
    for animal in _ANIMAL_TYPES:
        for adj in _SIZE_ADJECTIVES:
            pattern = r"(?i)(?<!NOT add a )(?<!not add a )\b" + _re.escape(adj) + r"\s+" + _re.escape(animal) + r"\b"
            prompt = _re.sub(pattern, animal, prompt)

    # Clean up double spaces
    prompt = _re.sub(r"  +", " ", prompt)
    return prompt


def _validate_grok_prompt(clear_instructions, fmt="news", groups=None, idea_id=""):
    """Check prompt for required guardrail elements. Returns list of warnings."""
    warnings = []
    ci_lower = clear_instructions.lower()
    groups = groups or []

    if "raccoon" in groups:
        has_count = ("exactly three" in ci_lower or "exactly 3" in ci_lower
                     or "three raccoons" in ci_lower or "not four" in ci_lower)
        if not has_count:
            warnings.append("MISSING: Raccoon count lock (EXACTLY THREE)")

    if fmt == "cctv":
        if "camera" not in ci_lower or ("do not" not in ci_lower and "don't" not in ci_lower):
            warnings.append("MISSING: Anti-CCTV-camera-prop instruction for cctv format")

    if "do not" not in ci_lower and "don't" not in ci_lower:
        warnings.append("MISSING: Negative instructions (tell Grok what NOT to do)")

    if "same size" not in ci_lower and "same height" not in ci_lower:
        if len(groups) > 0:
            warnings.append("MISSING: Subject size uniformity rule")

    if "shadow" not in ci_lower and "lighting" not in ci_lower:
        warnings.append("MISSING: Lighting/shadow matching instruction")

    if "plates_signed" not in ci_lower and "plate_0100" not in ci_lower:
        warnings.append("MISSING: plates_signed/ folder reference — Boston must upload from plates_signed/")

    # P17: Celebrity prop contamination check
    celeb_bans = _detect_celebrity_bans(ci_lower)
    if celeb_bans and "contamination guard" not in ci_lower:
        celeb_names = [name for name in CELEBRITY_PROP_BANS if name in ci_lower]
        if celeb_names:
            warnings.append(f"INFO: Celebrity detected ({', '.join(celeb_names[:3])}) — P17 counter-bans will be auto-injected")

    return warnings


def _build_grok_prompt(idea, idea_id=""):
    """Build a complete, guardrailed Grok composite prompt from an idea dict.

    Universal guardrail assembly — every principle applies to every prompt:
    1. Hero proportion enforcement (FIRST in output — P2)
    2. Main content (clear_instructions or auto-generated)
    3. Subject group rules: count lock, size lock, identity lock (P3, P4)
    4. Universal size uniformity (P3)
    5. Universal realism rules (shadows, scale, lighting)
    6. Camera perspective rules (P5)
    7. Contamination bans (P6)
    8. Negative instructions (P1)
    9. Background preservation (P8)
    10. Auto-strip size-differential language (P4)
    """
    clear = idea.get("clear_instructions", "")
    fmt = idea.get("format", "news")
    plate = idea.get("plate", "plate_0102.jpg")
    title = (idea.get("title", "") + " " + idea_id).lower()
    desc = idea.get("desc", "")
    full_text = (title + " " + desc + " " + clear).lower()

    # Detect all subject groups present
    groups = _detect_subject_groups(full_text)

    plate_base = Path(plate).stem if "/" in plate else plate.replace(".jpg", "").replace(".png", "")
    plate_loc = ""
    for pk, pi in PLATE_CATALOG.items():
        if pk in plate_base or plate_base in pk:
            surface_key = pi.get("surface", "")
            plate_loc = SURFACE_CONTEXT.get(surface_key, "the cabin property")
            break
    if not plate_loc:
        plate_loc = "the cabin property"

    if clear:
        prompt = clear
    else:
        first_beat = ". ".join(desc.split(".")[:2]).strip()
        prompt = f"Use the uploaded plate photo ({plate}) of {plate_loc}.\n\n{first_beat}."

    # P2: Hero proportion enforcement goes FIRST
    proportion_block = _build_proportion_block(prompt + " " + title, groups)

    sections = []
    if proportion_block:
        sections.append(proportion_block)

    sections.append(prompt.rstrip())

    # P3 + P4: Subject group rules (count, size, identity)
    # Skip blocks whose content is already present in clear_instructions
    has_group_size_lock = False
    clear_lower = clear.lower()
    for group_key in groups:
        group = GROK_SUBJECT_GROUPS[group_key]
        if group["count_lock"]:
            has_count_in_clear = ("not four" in clear_lower or "exactly three" in clear_lower
                                 or "three raccoons" in clear_lower)
            if not has_count_in_clear:
                sections.append(group["count_lock"])
        if group["size_lock"]:
            if "SAME SIZE" not in clear and "same size" not in clear:
                sections.append(group["size_lock"])
            has_group_size_lock = True
        if group["identity_lock"]:
            sections.append(group["identity_lock"])

    # P3: Universal size uniformity — skip if group-specific locks already handle it
    if not has_group_size_lock:
        sections.append(GROK_UNIVERSAL_SIZE_RULE)

    # Realism: shadows, scale, lighting match
    sections.append(GROK_UNIVERSAL_REALISM)

    # P5: Camera perspective
    format_rule = GROK_FORMAT_RULES.get(fmt)
    if format_rule:
        sections.append(format_rule)

    # P6: Contamination bans — skip if clear_instructions already has explicit bans
    if "DO NOT ADD ANY OF THESE" not in clear and "Do NOT add ANY" not in clear:
        sections.append(GROK_CONTAMINATION_BANS)

    # ALWAYS inject vehicle ban — Grok keeps hallucinating buses
    if "bus" not in clear.lower():
        sections.append(GROK_VEHICLE_BAN)

    # P17: Celebrity prop contamination guard
    celeb_bans = _detect_celebrity_bans(full_text)
    if celeb_bans:
        sections.append("CELEBRITY CONTAMINATION GUARD — CRITICAL:\n" + "\n".join(celeb_bans))

    # P1: Negative instructions — skip if clear_instructions already covers bans
    has_text_ban = "no text" in clear.lower() or "no labels" in clear.lower()
    has_camera_ban = "no cctv" in clear.lower() or "no camera" in clear.lower()
    if not (has_text_ban and has_camera_ban):
        sections.append(GROK_NEGATIVE_INSTRUCTIONS)

    # P8: Background preservation
    sections.append(
        "Keep EVERYTHING else in the photo exactly as-is. Do not change, move, or remove "
        "any background elements. Photorealistic, match existing lighting exactly."
    )

    # P16: Sign preservation (sign is pre-composited into plates_signed/)
    # plate_0100 has no sign (too many obstructions) — skip this block for it
    plate_lower = plate.lower()
    has_sign = "plate_0100" not in plate_lower and "100_" not in plate_lower
    if has_sign:
        sections.append(
            'SIGN PRESERVATION: The "Scenic 515 Cabins" sign is ALREADY in this photo. '
            "Do NOT modify, move, cover, or redraw it. Do NOT add other signs or text. "
            "Place all subjects AWAY from the sign."
        )

    full_prompt = "\n\n".join(sections)

    # P4: Auto-strip size-differential language for ALL subject groups
    if groups:
        full_prompt = _auto_strip_size_language(full_prompt, groups)

    warnings = _validate_grok_prompt(full_prompt, fmt, groups, idea_id)

    return full_prompt, warnings


def cmd_grok_prompt(idea_id):
    """Output a complete, guardrailed Grok prompt for a given idea, ready to paste."""
    idea = VIDEO_IDEAS.get(idea_id)
    source = "VIDEO_IDEAS"

    if not idea:
        bank_path = Path(__file__).resolve().parent.parent / "atlas_data" / "515" / "ideas_bank.json"
        if bank_path.exists():
            import json
            bank = json.loads(bank_path.read_text())
            for entry in bank:
                if entry.get("id") == idea_id:
                    idea = entry
                    source = "ideas_bank.json"
                    break

    if not idea:
        print(f"  ERROR: Idea '{idea_id}' not found in VIDEO_IDEAS or ideas_bank.json")
        return

    prompt, warnings = _build_grok_prompt(idea, idea_id)

    plate_ref = idea.get('plate', 'none')
    plate_lower = plate_ref.lower()
    is_0100 = "plate_0100" in plate_lower or "100_" in plate_lower
    upload_folder = "plates_signed/ (NO sign — plate_0100 exception)" if is_0100 else "plates_signed/ (has 515 sign)"

    print(f"\n{'='*60}")
    print(f"  GROK PROMPT — {idea_id}")
    print(f"  Source: {source}")
    print(f"  Format: {idea.get('format', 'news')}")
    print(f"  Plate: {plate_ref}")
    print(f"  Upload from: {upload_folder}")
    print(f"{'='*60}\n")

    if warnings:
        print("  ⚠ VALIDATION WARNINGS:")
        for w in warnings:
            print(f"    • {w}")
        print()

    print(prompt)
    print(f"\n{'='*60}")

    try:
        import subprocess
        subprocess.run(["pbcopy"], input=prompt.encode(), check=True)
        print("  COPIED TO CLIPBOARD")
    except Exception:
        print("  (could not copy to clipboard — paste from above)")

    print(f"{'='*60}\n")


AQUATIC_ANIMALS = {"bass", "fish", "catfish", "crappie", "perch", "trout", "largemouth"}
WATER_CONTEXT_WORDS = {
    "water", "lake", "dock", "boat", "swim", "splash", "flop out of",
    "jump from", "flopping", "bucket", "caught", "fishing", "reel",
    "river", "pond", "creek", "shore", "underwater", "net",
}

AQUATIC_TO_RACCOON_VERBS = {
    "flops": "scurries",
    "flopping": "scampering",
    "flop": "scurry",
    "swims": "runs",
    "swimming": "running",
    "swim": "run",
    "splashes": "crashes",
    "fins": "paws",
    "tail fin": "bushy tail",
    "scales": "fur",
    "gills": "nose",
    "mouth gaping": "mouth chattering",
}


def _substitute_aquatic_on_land(scene_prompt, surface):
    """Replace aquatic animals with the Rowdy Raccoons when there's no water context."""
    prompt_lower = scene_prompt.lower()

    has_water = any(w in prompt_lower for w in WATER_CONTEXT_WORDS)
    if has_water:
        return scene_prompt, False

    has_aquatic = any(a in prompt_lower for a in AQUATIC_ANIMALS)
    if not has_aquatic:
        return scene_prompt, False

    dock_or_lake = surface in ("dock", "lake")
    if dock_or_lake:
        return scene_prompt, False

    result = scene_prompt
    for animal in sorted(AQUATIC_ANIMALS, key=len, reverse=True):
        import re as _re
        pattern = _re.compile(r'\b' + _re.escape(animal) + r'(s?)\b', _re.IGNORECASE)
        def _repl(m):
            word = "raccoons" if m.group(1) else "raccoon"
            if m.group(0)[0].isupper():
                return word.capitalize()
            return word
        result = pattern.sub(_repl, result)

    for old_verb, new_verb in AQUATIC_TO_RACCOON_VERBS.items():
        result = result.replace(old_verb, new_verb)

    result = result.replace("giant raccoon", "three rowdy raccoons")
    result = result.replace("Giant raccoon", "Three rowdy raccoons")
    result = result.replace("massive raccoon", "three rowdy raccoons")
    result = result.replace("7-foot raccoon", "three rowdy raccoons")
    result = result.replace("huge raccoon", "three rowdy raccoons")

    return result, True


# ──────────────────────────────────────────────────────────────
# PROMPT HOLE DETECTOR — finds missing narrative beats and auto-fixes
# A 15-second video needs: SETUP (0-3s) → EVENT (3-8s) → CLIMAX (8-12s) → RESOLUTION (12-15s)
# This catches prompts that are missing exits, reactions, or aftermath.
# ──────────────────────────────────────────────────────────────

PROMPT_HOLE_RULES = [
    # NOTE: Sky/vehicle/creature EXIT rules are WARN-ONLY, not auto-fix.
    # Kling V3 Pro CANNOT make large objects leave the frame — the starting image
    # locks composition. Wasted $3.36 proving this (UFO v3+v4, Jul 20 2026).
    # If an exit is critical, do it in FFmpeg post-production (scale/translate/fade).
    {
        "id": "sky_object_exit",
        "desc": "Sky object present but no exit — Kling CANNOT do this, skip or plan FFmpeg post",
        "trigger_keywords": ["ufo", "flying saucer", "spaceship", "spacecraft", "helicopter",
                             "drone", "blimp", "hot air balloon", "portal", "meteor"],
        "exit_keywords": ["zips away", "flies away", "shoots off", "disappears", "vanishes",
                          "rockets away", "blasts off", "speeds away", "streaks away",
                          "out of frame", "zip away", "flies off", "zips off", "gone"],
        "warn_only": True,
        "fix": "",
    },
    {
        "id": "vehicle_exit",
        "desc": "Vehicle present but no exit — Kling CANNOT do this, skip or plan FFmpeg post",
        "trigger_keywords": ["truck", "car", "ambulance", "fire truck", "bus", "tractor",
                             "bulldozer", "tank", "van", "sedan"],
        "exit_keywords": ["drives away", "peels out", "speeds off", "pulls away", "rumbles off",
                          "out of frame", "drives off", "rolls away", "roars off", "gone"],
        "warn_only": True,
        "fix": "",
    },
    {
        "id": "creature_exit",
        "desc": "Large creature present but no exit — Kling CANNOT do this, skip or plan FFmpeg post",
        "trigger_keywords": ["bigfoot", "sasquatch", "monster", "dinosaur", "giant",
                             "godzilla", "king kong", "alien creature"],
        "exit_keywords": ["runs away", "bolts", "crashes through", "disappears into",
                          "stomps off", "lumbers away", "vanishes", "charges off",
                          "out of frame", "gone", "retreats"],
        "warn_only": True,
        "fix": "",
    },
    {
        "id": "bystander_reaction",
        "desc": "Bystanders must REACT to dramatic events",
        "trigger_keywords": ["raccoon", "deer", "bear", "person", "people", "fish",
                             "armadillo", "cat", "dog", "squirrel"],
        "requires_event_keywords": ["abduct", "crash", "explod", "beam", "grab", "yank",
                                    "attack", "chase", "steal", "smash", "destroy",
                                    "launch", "rip", "slam", "throw", "ufo", "flying saucer",
                                    "monster", "bigfoot", "explosion"],
        "reaction_keywords": ["panic", "screech", "scramble", "flee", "cower", "stumble",
                              "freeze", "react", "terrified", "shocked", "screeching",
                              "chittering", "flailing", "running", "hiding", "ducking",
                              "backing away", "loses it"],
        "fix": (
            "The remaining {bystanders} erupt in panic — screeching, scrambling over each other, "
            "stumbling backwards, looking around wildly. Their reactions escalate as the event "
            "gets more dramatic. No subject stands still — everyone is moving, reacting, panicking. "
        ),
    },
    {
        "id": "aftermath_beat",
        "desc": "Every video needs a final beat — the aftermath moment",
        "trigger_keywords": ["*"],
        "aftermath_keywords": ["freeze", "stare", "look at each other", "silence",
                               "dust settles", "empty", "gone", "stunned", "motionless",
                               "beat of silence", "looks at", "they look"],
        "fix": (
            "A beat of stillness. The remaining subjects freeze, staring at where the action "
            "just happened. Then they slowly look at each other. "
        ),
    },
]


def _detect_prompt_holes(scene_prompt):
    """Scan a scene prompt for missing narrative beats. Returns (fixed_prompt, list_of_fixes)."""
    import re
    prompt_lower = scene_prompt.lower()
    fixes_applied = []

    for rule in PROMPT_HOLE_RULES:
        rule_id = rule["id"]

        # Check if this rule's triggers are present in the prompt (word boundary match)
        if rule.get("trigger_keywords") == ["*"]:
            triggered = True
        else:
            triggered = any(
                re.search(r'\b' + re.escape(kw) + r'\b', prompt_lower)
                for kw in rule.get("trigger_keywords", [])
            )

        if not triggered:
            continue

        # For bystander reactions, also need a dramatic EVENT present
        if "requires_event_keywords" in rule:
            has_event = any(
                re.search(r'\b' + re.escape(kw) + r'\b', prompt_lower)
                for kw in rule["requires_event_keywords"]
            )
            if not has_event:
                continue

        # Determine which check keywords to use
        if "exit_keywords" in rule:
            check_keywords = rule["exit_keywords"]
        elif "reaction_keywords" in rule:
            check_keywords = rule["reaction_keywords"]
        elif "aftermath_keywords" in rule:
            check_keywords = rule["aftermath_keywords"]
        else:
            continue

        # Check if the beat is already present
        beat_present = any(kw in prompt_lower for kw in check_keywords)

        if beat_present:
            continue

        # Warn-only rules print to terminal but do NOT inject text
        if rule.get("warn_only"):
            fixes_applied.append({
                "rule": rule_id,
                "desc": rule["desc"],
                "fix": "",
                "warn_only": True,
            })
            continue

        # Beat is MISSING — build the fix
        # Find which trigger keyword matched (for the template)
        matched_trigger = ""
        if rule.get("trigger_keywords") != ["*"]:
            for kw in rule["trigger_keywords"]:
                if re.search(r'\b' + re.escape(kw) + r'\b', prompt_lower):
                    matched_trigger = kw
                    break

        fix_text = rule["fix"]
        if "{element}" in fix_text:
            fix_text = fix_text.replace("{element}", matched_trigger or "object")
        if "{bystanders}" in fix_text:
            # Find what animals/subjects are bystanders
            bystander_types = []
            for kw in ["raccoon", "deer", "bear", "person", "fish", "armadillo",
                        "cat", "dog", "squirrel"]:
                if kw in prompt_lower:
                    bystander_types.append(kw + "s")
            fix_text = fix_text.replace("{bystanders}", " and ".join(bystander_types) if bystander_types else "subjects")

        fixes_applied.append({
            "rule": rule_id,
            "desc": rule["desc"],
            "fix": fix_text,
        })

    if not fixes_applied:
        return scene_prompt, []

    # Inject fixes at the END of the prompt, before any lighting/camera instructions
    # Split prompt: find where the "atmosphere" section starts (lighting, camera, etc.)
    atmo_markers = [
        "warm evening", "warm golden", "golden hour", "bright morning", "afternoon sun",
        "keep the same", "do not change the time", "single continuous shot",
        "static security camera", "filmed on a phone", "natural daylight",
        "dark with ambient", "moonlight",
    ]

    # Find the earliest atmosphere marker
    split_pos = len(scene_prompt)
    for marker in atmo_markers:
        idx = scene_prompt.lower().find(marker)
        if idx != -1 and idx < split_pos:
            # Back up to the start of this sentence
            sentence_start = scene_prompt.rfind(".", 0, idx)
            if sentence_start != -1:
                split_pos = min(split_pos, sentence_start + 1)
            else:
                split_pos = min(split_pos, idx)

    action_part = scene_prompt[:split_pos].rstrip()
    atmo_part = scene_prompt[split_pos:].lstrip()

    # Inject all fixes between action and atmosphere (skip warn-only)
    injected = action_part
    for f in fixes_applied:
        if f.get("warn_only") or not f["fix"].strip():
            continue
        injected += " " + f["fix"].strip()

    if atmo_part:
        injected += " " + atmo_part

    return injected, fixes_applied


def _enrich_prompt(scene_prompt, meta):
    """Wrap a scene prompt with physical/logical context grounding.

    BUDGET-FIRST: Scene_prompt gets priority. Boilerplate fills remaining space.
    Kling V3 Pro hard limit is 2500 chars. Old approach put 3000-4700 chars of
    boilerplate BEFORE the scene_prompt, which got completely truncated.
    New approach: scene_prompt first (~1600 chars), boilerplate after (~800 chars).
    """
    plate_name = meta.get("plate", "")
    surface_key = ""
    surface = "rural East Texas fishing cabin property"

    for plate_key, plate_info in PLATE_CATALOG.items():
        if plate_key in plate_name or Path(plate_name).stem in plate_key:
            surface_key = plate_info.get("surface", "")
            surface = SURFACE_CONTEXT.get(surface_key, surface)
            break

    scene_prompt, was_substituted = _substitute_aquatic_on_land(scene_prompt, surface_key)
    if was_substituted:
        print(f"  AUTO-SUBSTITUTION: Aquatic animal on dry land → Rowdy Raccoons")

    scene_prompt, verb_fixes = _auto_fix_weak_verbs(scene_prompt)
    if verb_fixes:
        print(f"  WEAK VERBS FIXED: {verb_fixes} replacements")

    beat_count = _count_action_beats(scene_prompt)
    if beat_count > KLING_MAX_ACTION_BEATS:
        print(f"  WARNING: {beat_count} action beats detected (max {KLING_MAX_ACTION_BEATS})")

    scene_prompt, holes_fixed = _detect_prompt_holes(scene_prompt)
    if holes_fixed:
        for h in holes_fixed:
            label = "WARN" if h.get("warn_only") else "FIXED"
            print(f"  [{label}] {h['desc']}")

    time_desc = {
        "dawn": "Golden pre-sunrise, warm shadows, mist",
        "morning": "Bright morning sun, crisp shadows",
        "afternoon": "Full Texas afternoon sun, sharp shadows",
        "evening": "Golden hour, long shadows, amber tones",
        "night": "Dark, moonlight, porch lights, deep shadows",
        "day": "Bright daytime, clear sky, natural sunlight",
    }.get(meta.get("time_of_day", "day"), "Natural daylight")

    prompt_lower = scene_prompt.lower()
    has_raccoons = "raccoon" in prompt_lower

    plate_lower = plate_name.lower()
    has_sign = "plate_0100" not in plate_lower and "100_" not in plate_lower

    # ── BUILD ENRICHED PROMPT — SCENE_PROMPT FIRST ──
    parts = []

    # 1. THE ACTION — most important, goes first so it never gets truncated
    parts.append(scene_prompt)

    # 2. CAMERA — locked static when sign is present (prevents sign drift)
    if has_sign:
        parts.append(
            "CAMERA: LOCKED STATIC — no pan, tilt, zoom, drift, or any camera movement. "
            "Frame stays identical first-to-last. Only subjects move."
        )

    # 3. LOCATION + LIGHTING — one compact line
    parts.append(f"Location: 515 Scenic Cabins on Lake Fork, TX — {surface}. Lighting: {time_desc}.")

    # 4. RACCOON IDENTITY — condensed from 1383 to ~280 chars
    if has_raccoons:
        parts.append(
            "THREE raccoons — always separate, never merge or overlap. Same body size, all adult.\n"
            "R1: lighter grey-brown fur, notched left ear (leader). "
            "R2: darker prominent mask markings (schemer). "
            "R3: oversized bushy striped tail (hothead). Wild raccoons, realistic anatomy."
        )

    # 5. REALISM — condensed from 1123 to ~200 chars
    parts.append(
        "Objects must exist in starting frame or enter from off-screen. "
        "Environment is ground truth — don't change buildings or terrain. "
        "Consistent lighting throughout. Single continuous shot, no cuts."
    )

    enriched = "\n\n".join(parts)

    budget_used = len(enriched)
    print(f"  Enriched prompt: {budget_used} chars (scene: {len(scene_prompt)}, "
          f"boilerplate: {budget_used - len(scene_prompt)})")

    return enriched


PROMPT_TEMPLATE_GUIDE = """
=== 515 SCENE PROMPT STRUCTURE (6 parts) ===
Good prompts follow this exact structure. Copy this and fill in each section:

1. CHARACTERS & ENTRANCE (who is in the scene, where they start, how they enter)
   "A [character] [enters from / is already standing at] [specific location in frame]..."

2. MOTION SEQUENCE (specific physical actions with body mechanics)
   Use vivid motion verbs: lurches, slams, stumbles, darts, waddles, flinches, recoils
   Describe body parts: "arms flailing, legs splayed, tail rigid, head ducked"

3. CAUSE & EFFECT (every action has a reaction)
   "He grabs the handle — it breaks off in his hand. She steps on the dock — it creaks under her weight."

4. CLIMAX BEAT (the punchline moment, the thing people screenshot)
   "The bass lands perfectly in the boat seat. The raccoon holds up a tiny sign."

5. ENVIRONMENT INTERACTION (scene reacts to the action)
   "Dust kicks up from the gravel. Water splashes onto the dock. Leaves rustle from the gust."

6. CONTINUITY LOCK (prevent Kling from drifting)
   "Keep the same [time of day] lighting throughout. Do not change lighting or time of day."

MINIMUM: 150 characters. GOOD: 300-600 characters. The VIDEO_IDEAS prompts that work are 400-800 chars.
"""


NEGATIVE_PROMPT_FULL = (
    "blur, distort, morphing, warping, melting, deformed, cartoon, anime, "
    "illustration, UI elements, "
    "extra limbs, floating objects without support, sliding feet, background shifting, "
    "inconsistent physics, subjects merging into each other, "
    "disappearing subjects, objects appearing from thin air, objects materializing, "
    "things teleporting, instant transitions, jump cuts, "
    "fish on dry land with no water nearby, animals in impossible locations, "
    "objects hovering without explanation, gravity defying without cause, "
    "day to night transition, lighting change, shadow direction change, "
    "background buildings moving or changing shape, "
    "new structures appearing that aren't in the starting frame"
)
PLATE_COOLDOWN_DAYS = 7

def _load_plate_usage():
    if PLATE_USAGE_FILE.exists():
        return json.loads(PLATE_USAGE_FILE.read_text())
    return {}

def _save_plate_usage(usage):
    PLATE_USAGE_FILE.write_text(json.dumps(usage, indent=2) + "\n")

def _record_plate_use(plate_name):
    usage = _load_plate_usage()
    today = datetime.now(CT).strftime("%Y-%m-%d")
    if plate_name not in usage:
        usage[plate_name] = []
    usage[plate_name].append(today)
    usage[plate_name] = usage[plate_name][-10:]
    _save_plate_usage(usage)

def check_plate_available(plate_name):
    usage = _load_plate_usage()
    dates = usage.get(plate_name, [])
    if not dates:
        return True
    today = datetime.now(CT)
    for d in dates:
        try:
            used = datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=CT)
            if (today - used).days < PLATE_COOLDOWN_DAYS:
                return False
        except ValueError:
            continue
    return True

def plate_last_used(plate_name):
    usage = _load_plate_usage()
    dates = usage.get(plate_name, [])
    return dates[-1] if dates else "never"


def analyze_video_motion(video_path, interval=0.25):
    """Extract motion timeline from actual video frames.

    Returns list of (timestamp, intensity) sorted by time.
    Intensity = mean pixel difference between consecutive frames.
    Higher = more motion = something happened at that exact moment.
    """
    from PIL import Image
    import numpy as np

    tmp = Path(tempfile.mkdtemp(prefix="515_motion_"))
    dur_str = _video_info(video_path)
    try:
        parts = dur_str.split(":")
        duration = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    except Exception:
        duration = 15.0

    # Extract frames at interval using ffmpeg
    cmd = [
        FFMPEG, '-y', '-i', str(video_path),
        '-vf', f'fps=1/{interval},scale=270:480',
        '-q:v', '8',
        str(tmp / 'frame_%04d.png')
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        print(f"  Frame extraction failed: {r.stderr[-200:]}")
        return []

    frames = sorted(tmp.glob('frame_*.png'))
    if len(frames) < 3:
        for f in frames:
            f.unlink()
        tmp.rmdir()
        return []

    # Compute frame-to-frame differences
    timeline = []
    prev = np.array(Image.open(frames[0]).convert('L'), dtype=float)
    for i, fp in enumerate(frames[1:], 1):
        curr = np.array(Image.open(fp).convert('L'), dtype=float)
        diff = np.mean(np.abs(curr - prev))
        timestamp = round(i * interval, 2)
        timeline.append((timestamp, round(float(diff), 2)))
        prev = curr

    # Cleanup
    for f in frames:
        f.unlink()
    tmp.rmdir()

    return timeline


def find_motion_events(timeline, min_gap=1.5):
    """Find significant motion spikes in the timeline.

    Uses TWO detection methods for maximum accuracy:
    1. Absolute intensity — frames with motion above the 75th percentile
    2. Acceleration — frames where motion JUMPS sharply from the previous frame
       (a sudden increase = an impact, crash, slam, etc.)

    Returns list of (timestamp, intensity, rank) where rank 1 = biggest event.
    min_gap prevents two events closer than min_gap seconds.
    """
    if not timeline:
        return []

    intensities = [d for _, d in timeline]
    sorted_i = sorted(intensities)

    # Method 1: 75th percentile threshold for absolute intensity
    p75 = sorted_i[int(len(sorted_i) * 0.75)]
    abs_threshold = max(p75, 5.0)

    # Method 2: acceleration (frame-to-frame increase in motion)
    accels = []
    for i in range(1, len(timeline)):
        t = timeline[i][0]
        jump = timeline[i][1] - timeline[i-1][1]
        accels.append((t, jump, timeline[i][1]))

    accel_values = [a for _, a, _ in accels if a > 0]
    accel_threshold = 3.0
    if accel_values:
        sorted_a = sorted(accel_values)
        accel_threshold = max(sorted_a[int(len(sorted_a) * 0.75)], 3.0)

    # Combine candidates from both methods
    # Score = intensity + acceleration bonus (impacts score highest)
    scored = {}
    for t, d in timeline:
        if d >= abs_threshold:
            scored[t] = scored.get(t, 0) + d

    for t, jump, intensity in accels:
        if jump >= accel_threshold:
            scored[t] = scored.get(t, 0) + jump * 2.0

    if not scored:
        # Nothing detected — return the single highest-motion frame
        best_t, best_d = max(timeline, key=lambda x: x[1])
        return [(best_t, best_d, 1)]

    # Sort by score descending, pick top events with min_gap spacing
    candidates = sorted(scored.items(), key=lambda x: -x[1])
    events = []
    for t, score in candidates:
        too_close = any(abs(t - et) < min_gap for et, _, _ in events)
        if not too_close:
            actual_intensity = next((d for ts, d in timeline if ts == t), score)
            events.append((t, actual_intensity, 0))
        if len(events) >= 8:
            break

    # Rank by intensity (1 = biggest)
    events.sort(key=lambda x: -x[1])
    ranked = [(t, d, rank + 1) for rank, (t, d, _) in enumerate(events)]
    ranked.sort(key=lambda x: x[0])

    return ranked


def sync_audio_to_video(idea_id, video_path):
    """Analyze actual video motion, then build perfectly timed audio spec.

    This replaces guesswork. The audio cues land exactly where the action
    happens in the generated video, not where we hoped it would happen.
    """
    meta = VIDEO_IDEAS[idea_id]
    prompt = meta["scene_prompt"]
    time_of_day = meta.get("time_of_day", "afternoon")
    format_type = meta.get("format", "news")

    print(f"  Analyzing video motion (frame-by-frame)...")
    timeline = analyze_video_motion(video_path)
    events = find_motion_events(timeline, min_gap=1.0)

    print(f"  Found {len(events)} motion events:")
    for t, intensity, rank in events:
        label = "BIGGEST" if rank == 1 else f"#{rank}"
        print(f"    {t:>6.2f}s  intensity={intensity:>6.1f}  [{label}]")

    # Build layers starting with ambient + overlay
    layers = []

    ambient = AMBIENT_MAP.get(time_of_day, "afternoon_nature.mp3")
    if (SFX_DIR / ambient).exists():
        layers.append({"file": ambient, "start": 0.0, "volume_db": -8, "in_scene": True, "loop": True})
    elif (SFX_DIR / "ambient_night.mp3").exists():
        layers.append({"file": "ambient_night.mp3", "start": 0.0, "volume_db": -8, "in_scene": True, "loop": True})

    if format_type == "news" and (SFX_DIR / "news_sting_short.mp3").exists():
        layers.append({"file": "news_sting_short.mp3", "start": 0.0, "volume_db": -10, "in_scene": False})

    # Continuous ambient loops based on prompt content (P9: scene atmosphere)
    SCENE_AMBIENT_KEYWORDS = {
        "ufo_hum.mp3": ["ufo", "flying saucer", "saucer", "hover", "tractor beam", "spaceship"],
        "lake_water.mp3": ["lake", "water", "shore", "dock", "boat"],
        "crowd_murmur.mp3": ["crowd", "audience", "spectators", "onlookers"],
    }
    prompt_lower = prompt.lower()
    for sfx_file, keywords in SCENE_AMBIENT_KEYWORDS.items():
        if any(kw in prompt_lower for kw in keywords):
            if (SFX_DIR / sfx_file).exists():
                layers.append({"file": sfx_file, "start": 0.0, "volume_db": -12, "in_scene": True, "loop": True})

    # Detect scene context for smarter sound selection
    SCENE_SOUND_OVERRIDES = {
        "ufo": {
            "man_grunt.mp3": ("ufo_zip.mp3", -10),
            "heavy_thud.mp3": ("ufo_zip.mp3", -12),
            "running_gravel.mp3": ("wind_gust.mp3", -14),
            "card_slam.mp3": ("ufo_zip.mp3", -10),
            "chair_scrape.mp3": ("wind_gust.mp3", -16),
            "briefcase_drop.mp3": ("ufo_zip.mp3", -12),
            "footsteps_wood.mp3": ("wind_gust.mp3", -18),
            "golf_swing.mp3": ("wind_gust.mp3", -14),
            "gasp.mp3": ("raccoon_screech.mp3", -14),
            "laughter.mp3": ("raccoon_sounds.mp3", -14),
            "man_yell.mp3": ("raccoon_screech.mp3", -12),
            "clap_single.mp3": ("ufo_zip.mp3", -12),
            "fish_flop.mp3": ("wind_gust.mp3", -16),
        },
        "water": {
            "running_gravel.mp3": ("lake_water.mp3", -16),
            "heavy_thud.mp3": ("splash_large.mp3", -14),
        },
        "poker": {
            "heavy_thud.mp3": ("table_crash.mp3", -16),
            "running_gravel.mp3": ("chair_scrape.mp3", -18),
        },
    }
    scene_ctx = None
    if any(w in prompt_lower for w in ["ufo", "saucer", "beam", "tractor", "abduct"]):
        scene_ctx = "ufo"
    elif any(w in prompt_lower for w in ["poker", "chips", "card table", "gambling"]):
        scene_ctx = "poker"
    elif any(w in prompt_lower for w in ["lake", "fishing", "dock", "boat", "water"]):
        scene_ctx = "water"

    # Parse prompt for sound keywords, in order of appearance
    skip_words = ['lighting', 'camera', 'filmed', 'photorealistic', 'cinematic',
                  'static', '4k', 'handheld', 'detail', 'angle', 'important',
                  'must', 'remain', 'visible', 'throughout', 'never merge',
                  'keep the same', 'do not change', 'conditions']

    sentences = [s.strip() for s in prompt.replace('. ', '.|').split('|') if s.strip()]
    action_sentences = []
    for s in sentences:
        lower = s.lower()
        if any(skip in lower for skip in skip_words):
            continue
        if len(s) > 15:
            action_sentences.append(s)
    if not action_sentences:
        action_sentences = sentences[:5]

    # Extract sound cues from prompt in order
    sound_cues = []
    used_files = set()
    for sentence in action_sentences:
        lower = sentence.lower()
        for keyword, (sfx_file, vol) in SOUND_KEYWORDS.items():
            if not re.search(r'\b' + re.escape(keyword) + r'\b', lower):
                continue
            # Apply scene-context overrides
            if scene_ctx and scene_ctx in SCENE_SOUND_OVERRIDES:
                override = SCENE_SOUND_OVERRIDES[scene_ctx].get(sfx_file)
                if override:
                    sfx_file, vol = override
            if not (SFX_DIR / sfx_file).exists():
                continue
            if sfx_file in used_files:
                continue
            used_files.add(sfx_file)

            # Classify impact level
            loud_words = {'slam', 'slams', 'crash', 'flip', 'flips', 'splash',
                          'launch', 'kicks', 'roar', 'rips', 'rip'}
            is_big_impact = keyword in loud_words
            sound_cues.append({
                "file": sfx_file,
                "volume_db": vol,
                "is_big_impact": is_big_impact,
                "keyword": keyword,
            })

    if not events:
        # Fallback: spread sounds evenly if no motion detected
        print(f"  WARNING: No motion events detected — using fallback timing")
        n = len(sound_cues)
        for i, cue in enumerate(sound_cues):
            t = round(1.5 + (i / max(n - 1, 1)) * 12.0, 2)
            layers.append({
                "file": cue["file"],
                "start": t,
                "volume_db": cue["volume_db"],
                "in_scene": True,
            })
    else:
        # Match sounds to actual motion events
        # Big impacts → biggest motion spikes
        # Small sounds → smaller spikes or interpolated timestamps
        big_impacts = [c for c in sound_cues if c["is_big_impact"]]
        small_sounds = [c for c in sound_cues if not c["is_big_impact"]]

        events_by_rank = sorted(events, key=lambda x: x[2])
        used_events = set()

        # Assign big impacts to biggest spikes first
        for cue in big_impacts:
            for t, intensity, rank in events_by_rank:
                if rank not in used_events:
                    used_events.add(rank)
                    layers.append({
                        "file": cue["file"],
                        "start": t,
                        "volume_db": cue["volume_db"],
                        "in_scene": True,
                        "_synced_to": f"event#{rank} intensity={intensity}",
                    })
                    print(f"    Synced {cue['keyword']} ({cue['file']}) → {t}s (event #{rank}, intensity {intensity})")
                    break

        # Assign small sounds to remaining events or interpolate
        remaining_events = [e for e in events_by_rank if e[2] not in used_events]
        for i, cue in enumerate(small_sounds):
            if i < len(remaining_events):
                t, intensity, rank = remaining_events[i]
                used_events.add(rank)
                layers.append({
                    "file": cue["file"],
                    "start": t,
                    "volume_db": cue["volume_db"],
                    "in_scene": True,
                    "_synced_to": f"event#{rank} intensity={intensity}",
                })
                print(f"    Synced {cue['keyword']} ({cue['file']}) → {t}s (event #{rank}, intensity {intensity})")
            else:
                # No more events — place relative to existing events
                if events:
                    # Spread remaining sounds between first and last event
                    first_t = events[0][0]
                    last_t = events[-1][0]
                    spread = last_t - first_t if last_t > first_t else 10.0
                    n_remaining = len(small_sounds) - len(remaining_events)
                    offset = (i - len(remaining_events) + 1) / max(n_remaining, 1)
                    t = round(first_t + offset * spread, 2)
                else:
                    t = round(1.5 + i * 2.5, 2)
                layers.append({
                    "file": cue["file"],
                    "start": t,
                    "volume_db": cue["volume_db"],
                    "in_scene": True,
                    "_synced_to": "interpolated",
                })
                print(f"    Placed {cue['keyword']} ({cue['file']}) → {t}s (interpolated)")

    # Sort by start time
    layers.sort(key=lambda x: x["start"])

    spec = {"layers": layers, "synced": True, "events": [(t, d, r) for t, d, r in events]}
    return spec


# ──────────────────────────────────────────────────────────────
# SCENE AUDIO ANALYZER — fallback when no video exists yet
# (pre-generation planning only — sync_audio_to_video replaces
# this once the video is generated)
# ──────────────────────────────────────────────────────────────

def auto_audio_spec(idea_id):
    meta = VIDEO_IDEAS[idea_id]
    prompt = meta["scene_prompt"]
    time_of_day = meta.get("time_of_day", "afternoon")
    format_type = meta.get("format", "news")

    layers = []

    ambient = AMBIENT_MAP.get(time_of_day, "afternoon_nature.mp3")
    if (SFX_DIR / ambient).exists():
        layers.append({"file": ambient, "start": 0.0, "volume_db": -8, "in_scene": True, "loop": True})
    elif (SFX_DIR / "ambient_night.mp3").exists():
        layers.append({"file": "ambient_night.mp3", "start": 0.0, "volume_db": -8, "in_scene": True, "loop": True})

    if format_type == "news" and (SFX_DIR / "news_sting_short.mp3").exists():
        layers.append({"file": "news_sting_short.mp3", "start": 0.0, "volume_db": -10, "in_scene": False})

    skip_words = ['lighting', 'camera', 'filmed', 'photorealistic', 'cinematic',
                  'static', '4k', 'handheld', 'detail', 'angle', 'important',
                  'must', 'remain', 'visible', 'throughout', 'never merge',
                  'keep the same', 'do not change', 'conditions']

    sentences = [s.strip() for s in prompt.replace('. ', '.|').split('|') if s.strip()]
    action_sentences = []
    for s in sentences:
        lower = s.lower()
        if any(skip in lower for skip in skip_words):
            continue
        if len(s) > 15:
            action_sentences.append(s)

    if not action_sentences:
        action_sentences = sentences[:5]

    n = len(action_sentences)
    used_files = set()

    for i, sentence in enumerate(action_sentences):
        base_t = (i / max(n - 1, 1)) * 12.0 + 1.5
        lower = sentence.lower()
        match_count = 0

        for keyword, (sfx_file, vol) in SOUND_KEYWORDS.items():
            if not re.search(r'\b' + re.escape(keyword) + r'\b', lower):
                continue
            if not (SFX_DIR / sfx_file).exists():
                continue
            if sfx_file in used_files:
                continue
            used_files.add(sfx_file)
            t = round(base_t + match_count * 0.8, 1)
            match_count += 1
            layers.append({
                "file": sfx_file,
                "start": t,
                "volume_db": vol,
                "in_scene": True,
            })

    return {"layers": layers}


def check_sfx_availability(idea_id):
    spec = AUDIO_SPECS.get(idea_id) or auto_audio_spec(idea_id)
    missing = []
    for layer in spec.get("layers", []):
        sfx_path = SFX_DIR / layer["file"]
        if not sfx_path.exists():
            if layer["file"] not in missing:
                missing.append(layer["file"])
    return missing


def print_timing_map(idea_id):
    spec = AUDIO_SPECS.get(idea_id) or auto_audio_spec(idea_id)
    layers = spec.get("layers", [])
    if not layers:
        print("  No audio layers")
        return

    print(f"\n  AUDIO TIMING MAP ({len(layers)} layers):")
    print(f"  {'#':<4} {'TIME':<8} {'VOL':<7} {'FILE':<28} {'TYPE'}")
    print(f"  {'-'*60}")
    for i, layer in enumerate(layers):
        t = layer['start']
        vol = layer['volume_db']
        fname = layer['file']
        ltype = "LOOP" if layer.get('loop') else ("OVERLAY" if not layer.get('in_scene', True) else "SCENE")
        print(f"  {i:<4} {t:>5.1f}s  {vol:>4}dB  {fname:<28} {ltype}")
    print(f"  {'-'*60}")
    print(f"  Retime: python3 515_video_gen.py retime {idea_id} <layer#>=<seconds> ...")


# ──────────────────────────────────────────────────────────────
# VIDEO IDEAS — scene_prompt describes MOTION ONLY (image-to-video).
# Grok generates the starting frame with subjects already placed.
# Prompt tells Kling what HAPPENS, not what the scene looks like.
#
# IDEA RULES:
# - Absurd + specific = viral. "Raccoons playing poker" not "fish walks."
# - Each idea must make someone chuckle, like, and share.
# - Pop culture crossovers, animals doing human things, escalation.
# - Only use locations ON the property (cabins, road, deck, patio, sign).
# - NO dock, NO lake shots — the lake is down the road.
# - Prompts: describe every motion beat in detail, atmospheric micro-motions,
#   specific verbs with direction/speed, end-states described.
#
# GROK PROMPTING RULES (clear_instructions):
# Grok tends to: add extra subjects, make objects wrong size, add literal
# props for camera types (CCTV cameras, news desks), and make all animals
# look identical. Fight every one of these with explicit instructions:
#
# 1. COUNT LOCK: "There are EXACTLY THREE raccoons — no more, no fewer.
#    Count them: one, two, three. Do NOT add a fourth."
# 2. SIZE LOCK: Give size relative to a known object. "The UFO is 15 feet
#    wide — roughly the width of two cabins side by side." Never just say
#    "large" or "small."
# 3. SPATIAL LOCK: Use "above/below/left/right of" with a landmark.
#    "The UFO hovers 30 feet ABOVE the raccoons in the SKY, centered over
#    the grass clearing." Never assume Grok knows what "hovering" means.
# 4. IDENTITY LOCK: Each raccoon needs a unique physical tag AND a unique
#    pose/position. Same fur = Grok makes clones. Vary poses.
# 5. NO CAMERA PROPS: "This is shot FROM a security camera angle — do NOT
#    add a CCTV camera, pole, or label as a physical object in the scene.
#    The camera is the viewer's perspective, not a prop."
# 6. NEGATIVE INSTRUCTIONS: Tell Grok what NOT to do. "Do NOT add any
#    text labels, watermarks, or overlay graphics to the image."
# 7. ANTI-CONTAMINATION: Grok bleeds props from other ideas into new
#    images (poker chips appear on raccoons in non-poker scenes). Every
#    prompt MUST explicitly ban props from other videos: "Do NOT add
#    poker chips, playing cards, gambling items, gold chains, sunglasses,
#    or visors." List what doesn't belong, not just what does.
# 8. SIZE HIERARCHY: Describe the BIGGEST/most important element FIRST.
#    If the UFO is the star, lead with "A MASSIVE silver flying saucer
#    fills the upper third of the frame..." THEN add raccoons as secondary.
#    Grok makes the first-described element dominant.
# 9. SIGN VISIBILITY DEFAULT: ALL videos use plates_signed/ backgrounds
#    (with the 515 sign pre-composited). Boston uploads from plates_signed/
#    folder to Grok. plate_0100 is the ONLY exception (no sign — too many
#    obstructions). clear_instructions must always say "Upload plates_signed/..."
# ──────────────────────────────────────────────────────────────
VIDEO_IDEAS = {
    "cctv_raccoon_poker": {
        "format": "news",
        "title": "The Rowdy Raccoons",
        "plate": "vertical/raccoon_poker_start.png",
        "time_of_day": "evening",
        "headline": ("Rowdy Raccoons spotted gambling",
                     "at 515 Scenic Cabins on Lake Fork"),
        "clear_instructions": "Upload plates_signed/ version. Use the Grok-generated starting frame with raccoons already at the table.",
        "scene_prompt": (
            "Three separate distinct raccoons are already seated around the poker table on this wooden deck. "
            "IMPORTANT: There are exactly THREE raccoons and they must ALL remain visible as separate "
            "individual animals throughout the entire video. They never merge, overlap, or combine into "
            "each other. Each raccoon is a distinct separate animal at all times. "
            "Raccoon 1 (left side, lighter grey-brown fur, notched left ear — the leader) studies its "
            "cards closely, holding them up with both tiny paws, squinting with confidence. "
            "Raccoon 2 (center, darker prominent black mask markings — the schemer) leans sideways and "
            "peeks at Raccoon 1's hand sneakily, its eyes shifting back and forth. "
            "Raccoon 3 (right side, oversized bushy striped tail — the hothead) suddenly slams its cards "
            "down on the wooden table angrily. The impact makes the poker chips jump and scatter. "
            "Raccoon 3 stands up on its hind legs, grabs the edge of the poker table with both paws, "
            "and violently flips the entire table over. Poker chips and cards fly everywhere across the "
            "wooden deck — chips bounce off the deck railing and roll into the cracks between boards. "
            "The table legs screech against the wood as it topples. "
            "All three raccoons jump up — Raccoon 1 and Raccoon 2 start swatting at each other on the "
            "left side of the deck while Raccoon 3 grabs scattered chips on the right side, stuffing them "
            "into a pile with frantic paw movements. The deck boards creak under their scrambling weight. "
            "They wrestle and tumble across the deck, all three always visible and separate. "
            "Pure chaos and rowdy energy. A chair tips over and clatters against the railing. "
            "Keep the same bright daytime lighting throughout the entire video. "
            "Do not change the lighting or time of day. Same outdoor daytime conditions from start to finish. "
            "Single continuous shot, no cuts. "
            "Filmed on a phone camera, slightly grainy, handheld feel."
        ),
    },
    "news_raccoon_heist": {
        "format": "news",
        "title": "Raccoons execute cooler heist",
        "plate": "reference_bank/raccoon_heist_start.png",
        "time_of_day": "evening",
        "headline": ("Organized raccoon gang steals cooler",
                     "from 515 Scenic Cabins on Lake Fork"),
        "clear_instructions": (
            "Grok: Upload plates_signed/plate_0070.jpg (patio area, has 515 sign). Add EXACTLY THREE raccoons near a red cooler — "
            "no more, no fewer. Count them: one, two, three. Do NOT add a fourth. "
            "Raccoon 1 (LEFT — lighter grey-brown fur than the others, small notch on left ear): "
            "standing upright on hind legs near the swing, head turned left scanning. "
            "Raccoon 2 (CENTER-LEFT — darker fur with very prominent black mask): "
            "crouched low behind the cooler with tiny paws on one handle. "
            "Raccoon 3 (CENTER-RIGHT — oversized bushy striped tail): "
            "crouched on the other side gripping the other handle. "
            "All three wear tiny black ski masks pushed up on their foreheads. "
            "The cooler is a standard red Coleman-style cooler sitting on the concrete pad. "
            "Do NOT add poker chips, playing cards, gambling items, gold chains, sunglasses, or visors. "
            "Do NOT add CCTV cameras, poles, or camera equipment as props. "
            "Do NOT add any text, labels, or watermarks."
        ),
        "scene_prompt": (
            "Three raccoons in tiny black ski masks execute a perfectly coordinated cooler heist on this cabin patio. "
            "IMPORTANT: There are exactly THREE raccoons, each distinct and separate throughout the entire video. "
            "They never merge, overlap, or blend into each other. Each raccoon is its own individual animal at all times. "
            "Raccoon 1 (the lookout — lighter grey-brown fur, small notch on left ear, the leader) stands upright "
            "near the swing, snaps its head left, then right, then left again with rapid paranoid vigilance. Its "
            "notched ear twitches independently. It raises one tiny paw and gives a deliberate downward chopping "
            "hand signal — the 'go' signal. "
            "The instant the signal drops, Raccoon 2 (darker, more prominent black mask markings — the schemer) "
            "and Raccoon 3 (oversized bushy striped tail — the hothead) spring into action from behind the cooler. "
            "They grip the cooler handles with their tiny black paws, lift it off the ground with visible strain — "
            "their small bodies lean backward from the weight, legs splayed wide for balance. Raccoon 3's oversized "
            "bushy tail sticks straight out horizontal as counterweight. They waddle in synchronized lockstep, "
            "left foot right foot left foot, carrying the heavy cooler between them across the concrete pad toward "
            "the grass. The cooler scrapes against the concrete — a low grinding sound. Their claws click on the "
            "hard surface with each step. Movement is urgent but comically careful — bodies swaying side to side "
            "under the load. "
            "Raccoon 1 (lighter fur, notched ear) drops to all fours and scurries ahead, checking around the "
            "corner of the cabin, then waves them forward frantically with both paws. "
            "The two carrier raccoons pick up speed, the cooler swinging between them. Raccoon 2's dark mask "
            "markings make it look extra guilty as it glances back. All three disappear around the corner of "
            "the cabin together. The cooler bumps the corner of the building as they round it — paint chips "
            "flake off the siding. A single ice cube falls out and sits on the concrete, melting. "
            "Warm evening golden hour light throughout. Soft breeze moves the tree leaves overhead. Dust motes "
            "float in the low-angle sunbeams. Shadows stretch long across the concrete. "
            "Keep the same warm evening lighting throughout. Do not change the time of day or lighting conditions. "
            "Single continuous shot, no cuts. "
            "Filmed on a phone camera, slightly grainy, subtle handheld sway."
        ),
    },
    "cctv_shaq_door": {
        "format": "cctv",
        "title": "Shaq can't fit in the cabin",
        "plate": "reference_bank/shaq_door_start.png",
        "time_of_day": "afternoon",
        "headline": ("7-foot-1 man struggles to enter",
                     "cabin at 515 Scenic Cabins"),
        "clear_instructions": (
            "Grok: Upload plates_signed/plate_0010.jpg (cabin parking/entrance, has 515 sign). "
            "Add ONE person only — Shaq (Shaquille O'Neal), a very tall man "
            "(7-foot-1) in a Hawaiian shirt and shorts standing in front of the cabin door. "
            "He should be so tall that his head is ABOVE the top of the doorframe — the door "
            "only reaches his chest. He's ducking his head down, looking at the small door with "
            "a confused/amused expression. One hand rests on the doorframe above him (he can "
            "reach it easily), the other hand holds a small fishing tackle box at his side. "
            "The door is open. The man's shoulders are visibly wider than the doorframe. "
            "Do NOT add any other people, animals, text labels, or overlay graphics. "
            "Do NOT add CCTV cameras or news equipment as props."
        ),
        "scene_prompt": (
            "An enormous 7-foot-1 man in a Hawaiian shirt stands at the tiny cabin doorway, looking down at it "
            "with bewildered amusement. The porch boards creak and flex visibly under his weight with each shift "
            "of his feet. He ducks his head way down, bending his knees deeply, and tries to step through the "
            "doorframe sideways. His massive shoulder catches the doorframe — the whole frame shudders, dust "
            "falls from the header. He jerks back, rubs his shoulder, shakes his head. "
            "He tries again, leading with the other shoulder, bending even lower, practically in a full squat. "
            "The porch boards groan as he shifts his weight forward. He gets his upper body through but his "
            "hips catch on both sides of the frame. He's stuck — half inside, half outside. His legs are still "
            "on the porch, his torso and arms inside. He wiggles side to side trying to squeeze through, his "
            "Hawaiian shirt riding up. The door hinges strain and squeak with each push. "
            "He reaches one massive arm back outside and sets the tiny fishing tackle box down on the porch "
            "gently — the tackle box looks comically small in his enormous hand, like a matchbox. Lures rattle "
            "inside it as he places it down. Then he grabs both sides of the doorframe with his huge hands "
            "and pulls himself through with a dramatic lunge. A visible crack splits up the doorframe molding. "
            "Wood splinters peel outward. He stumbles inside and the door swings shut behind him — the slam "
            "rattles the cabin window in its frame. A beat of stillness. The tackle box sits alone on the porch. "
            "Then the cabin light flickers on through the window and you can see his silhouette — his head "
            "is pressed against the ceiling, bent sideways. The ceiling light fixture sways from where he "
            "bumped it. "
            "Bright afternoon sunlight, warm Texas summer light. Tree shadows dapple the cabin siding. "
            "A slight breeze rustles the leaves overhead. "
            "Keep the same bright daytime lighting throughout. Do not change lighting or time of day. "
            "Single continuous shot, no cuts. "
            "Static security camera angle, slight wide-angle distortion."
        ),
    },
    "news_lebron_vs_raccoons": {
        "format": "news",
        "title": "LeBron vs the Rowdy Raccoons",
        "plate": "reference_bank/lebron_bass_start.png",
        "time_of_day": "afternoon",
        "headline": ("LeBron James loses tug-of-war to raccoons",
                     "at 515 Scenic Cabins on Lake Fork"),
        "clear_instructions": (
            "Grok: Upload plates_signed/plate_0110.jpg (gravel road, has 515 sign). Add LeBron James — ONE tall athletic man in a "
            "Lakers jersey #23 and headband on the RIGHT side of the road, leaning back "
            "in a tug-of-war stance, gripping a thick rope with both hands. "
            "On the LEFT side of the road, add EXACTLY THREE raccoons holding the other end of "
            "the rope — no more, no fewer. Count them: one, two, three. Do NOT add a fourth. "
            "Raccoon 1 (FAR LEFT — lighter grey-brown fur, small notch on left ear): standing "
            "upright on hind legs, pointing one paw at LeBron aggressively. "
            "Raccoon 2 (CENTER-LEFT — darker fur with very prominent black mask): "
            "crouched low gripping the rope with both front paws, leaning back. "
            "Raccoon 3 (NEAR CENTER — oversized bushy striped tail): snarling, "
            "teeth bared, gripping the rope next to Raccoon 2. "
            "A fishing tackle box sits on the gravel BETWEEN LeBron and the raccoons — the prize. "
            "The 515 Scenic Cabins sign must be visible in the background. "
            "Do NOT add poker chips, playing cards, gambling items, gold chains. "
            "Do NOT add news desks, microphones, reporters, text labels, or overlay graphics. "
            "Do NOT add CCTV cameras or any camera equipment as props."
        ),
        "scene_prompt": (
            "LeBron James in a Lakers jersey squares off against three raccoons on this gravel road in a "
            "tug-of-war over a fishing tackle box. "
            "IMPORTANT: Three distinct raccoons, always separate, never merging or overlapping. "
            "Raccoon 1 (lighter grey-brown fur, small notch on left ear — the leader) stands tall on hind "
            "legs behind the other two, barking orders and pointing with one paw. "
            "Raccoon 2 (darker, more prominent black mask — the schemer) grips the rope with both front "
            "paws, leaning back, hind claws digging into the gravel and kicking up small dust puffs. "
            "Raccoon 3 (oversized bushy striped tail — the hothead) bites the rope with its teeth and "
            "pulls sideways, growling, claws scraping across the gravel with an audible scratching sound. "
            "LeBron pulls hard — his sneakers slide on loose gravel, leaving drag marks. He leans back, "
            "arms straining, jersey stretching. The tackle box slides one inch toward him. He grins. "
            "Raccoon 1 drops to all fours, sprints to the rope, and all three raccoons yank together — "
            "the rope snaps taut, LeBron lurches forward two full steps, stumbling, arms windmilling. "
            "The tackle box slides back toward the raccoons. Lures and hooks rattle inside it. "
            "LeBron digs in, wraps the rope around his forearm, pulls with his whole body. Raccoon 3 "
            "lets go of the rope, charges straight at LeBron, and scurries up his leg. LeBron drops the "
            "rope immediately, hopping on one foot, swatting at the raccoon climbing his shorts. "
            "Raccoon 2 seizes the moment — drags the tackle box backward across the gravel by its handle, "
            "the box bumping over small rocks. Raccoon 1 grabs the other side. They waddle off together "
            "with the box between them, Raccoon 3 leaps off LeBron and scurries after them. "
            "LeBron stands alone on the gravel road, rope limp in his hands, watching three raccoons "
            "disappear around the 515 sign with his tackle box. He shakes his head slowly. "
            "Bright afternoon sunlight, warm. Gravel dust hangs in the air from the scuffle. "
            "The 515 Scenic Cabins sign is visible in the background throughout. "
            "Keep the same bright daytime lighting throughout. Do not change lighting or time of day. "
            "Single continuous shot, no cuts. "
            "Filmed on a phone camera, slightly grainy, handheld feel."
        ),
    },
    "news_kevin_hart_scared": {
        "format": "news",
        "title": "Kevin Hart terrified at the cabins",
        "plate": "reference_bank/kevin_hart_start.png",
        "time_of_day": "afternoon",
        "headline": ("Kevin Hart refuses to stay at cabins",
                     "after terrifying encounter at Lake Fork"),
        "clear_instructions": (
            "Grok: Upload plates_signed/plate_0090.jpg (cabin exterior, has 515 sign). "
            "Add ONE person only — Kevin Hart, "
            "a short man (5-foot-2) in designer clothes (nice jacket, clean sneakers, looking "
            "completely out of place at a fishing cabin). He stands near the cabin entrance "
            "looking deeply uneasy — hunched shoulders, hands close to his chest, eyes "
            "wide, scanning the trees like something is about to jump out. A squirrel sits on "
            "a nearby railing behind him, and a small frog sits on the ground near his feet. "
            "Do NOT add any other people or animals beyond the one man, one squirrel, one frog. "
            "Do NOT add poker chips, playing cards, gambling items, gold chains. "
            "Do NOT add news desks, microphones, reporters, text labels, or CCTV cameras as props. "
            "Do NOT add any text or watermarks."
        ),
        "scene_prompt": (
            "Kevin Hart stands on this wooden cabin deck looking deeply uncomfortable and scared. He's hunched "
            "over with his hands near his chest, eyes darting left and right. A squirrel runs across the deck "
            "railing behind him — he LEAPS straight up, both feet off the ground, arms flailing, stumbles "
            "backward into the picnic table and knocks over a drink. He catches his breath, stands up straight, "
            "tries to act cool, brushes off his jacket. "
            "Then a frog croaks loudly from the grass. Kevin whips around toward the sound, freezes completely "
            "still, staring at the grass with wide terrified eyes. He slowly backs away from the deck edge "
            "on his tiptoes, each step exaggerated and careful. His hands are up in front of him defensively. "
            "A bird flies out of a tree overhead with a sudden flutter of wings. Kevin ducks down into a full "
            "crouch, arms over his head, then immediately jumps up and starts speed-walking toward the cabin "
            "door, looking over his shoulder every two steps. He reaches the door, yanks it open, darts inside, "
            "and slams it shut. A beat later, the curtain in the cabin window peels back slightly — one wide "
            "eye peeks out. "
            "Bright warm afternoon sunlight. Gentle breeze moves tree branches and leaves. Dappled shadows "
            "on the deck shift slightly. The drink he knocked over drips off the picnic table edge. "
            "Keep the same bright daytime lighting throughout. Do not change lighting or time of day. "
            "Single continuous shot, no cuts. "
            "Filmed on a phone camera, slightly grainy, handheld sway."
        ),
    },
    "news_raccoon_bbq": {
        "format": "news",
        "title": "Raccoons take over the BBQ",
        "plate": "reference_bank/raccoon_bbq_start.png",
        "time_of_day": "afternoon",
        "headline": ("Raccoons operating illegal BBQ restaurant",
                     "at 515 Scenic Cabins on Lake Fork"),
        "clear_instructions": (
            "Grok: Upload plates_signed/plate_0070.jpg (patio area with firepit, has 515 sign). "
            "Add EXACTLY THREE raccoons — no more, no fewer. Count: one, two, three. "
            "Do NOT add a fourth raccoon. "
            "Raccoon 1 (BY A PORTABLE GRILL — lighter grey-brown fur, small notch on left ear, tallest): "
            "standing behind a portable charcoal grill wearing a tiny white chef hat and "
            "miniature apron, holding tiny tongs in its paws. "
            "Raccoon 2 (NEAR THE PATIO — darker fur with very prominent black mask): "
            "standing upright near a folding table wearing a tiny bow tie, holding a small notepad "
            "in one paw like a waiter. "
            "Raccoon 3 (SEATED — oversized bushy striped tail visible): "
            "sitting at the folding table wearing tiny reading glasses, "
            "studying a piece of paper (menu) on the table. "
            "Visible smoke rising from the grill. "
            "Do NOT add poker chips, playing cards, gambling items, gold chains. "
            "Do NOT add news desks, microphones, CCTV cameras, or text labels as props. "
            "Do NOT add any text, watermarks, or overlay graphics."
        ),
        "scene_prompt": (
            "Three raccoons are running a fully operational BBQ restaurant at the cabin's covered deck area. "
            "IMPORTANT: Three distinct raccoons, always separate, never merging or overlapping. "
            "Raccoon 1 (the chef — lighter grey-brown fur, small notch on left ear, the leader) stands on "
            "a step stool behind the barrel grill wearing a tiny white hat and apron. It flips something on "
            "the smoking grill with tiny tongs — a burst of flame shoots up and the chef leans back dramatically, "
            "nearly falling off the step stool, catches itself with one paw on the grill handle. The step stool "
            "wobbles and scrapes against the deck boards. It recovers, flips the tongs expertly, and plates "
            "the food onto a tiny plate with deliberate garnishing movements — placing a single leaf on top "
            "with its tiny clawed fingers. Grease sizzles and pops on the hot grill surface. "
            "Raccoon 2 (the waiter — darker, more prominent black mask markings, the schemer) "
            "wearing a tiny bow tie takes the plate and carries it across the deck on one upturned paw, walking "
            "upright on hind legs with exaggerated fine-dining posture — chest out, nose up, free paw behind "
            "its back. Its claws tap on the deck boards with each careful step. It sets the plate down in "
            "front of Raccoon 3 with a small bow, its dark mask making it look absurdly formal. "
            "Raccoon 3 (the customer — oversized bushy striped tail, the hothead) wearing "
            "tiny reading glasses inspects the food closely. Leans in, sniffs. Looks up at the waiter with "
            "visible contempt. Pushes the plate away with one paw dismissively — the plate slides across the "
            "picnic table and bumps a condiment bottle. Raccoon 3 holds up the menu and points at something "
            "else aggressively, tapping the paper with one claw so hard it tears a small hole. Its bushy tail "
            "puffs up with indignation, bristling outward. The waiter throws both paws up in exasperation, "
            "turns around, and waddles back to the chef with the rejected plate. "
            "The chef raccoon (lighter fur, notched ear) looks at the returned plate, looks at the waiter, "
            "and angrily throws the tiny tongs down — they clatter off the grill and bounce on the deck. "
            "Smoke billows from the unattended grill behind it. "
            "Bright warm afternoon sunlight. Smoke drifts from the grill, catching the light. Tree leaves "
            "shift overhead in a gentle breeze. "
            "Keep the same bright daytime lighting throughout. Do not change lighting or time of day. "
            "Single continuous shot, no cuts. "
            "Filmed on a phone camera, slightly grainy, handheld feel."
        ),
    },
    "news_man_retires": {
        "format": "news",
        "title": "Man quits job to fish at Lake Fork",
        "plate": "reference_bank/man_retires_start.png",
        "time_of_day": "dawn",
        "headline": ("Dallas man quits job after",
                     "one night at 515 Scenic Cabins"),
        "clear_instructions": (
            "Grok: Upload plates_signed/plate_0110.jpg (gravel road, has 515 sign). Add ONE person only — a man in "
            "a full business suit (jacket, tie, dress shoes) standing in the middle of the gravel "
            "road. He holds a briefcase in his right hand and a fishing rod in his left hand. "
            "He looks conflicted, glancing between the two objects. "
            "The 515 Scenic Cabins sign must be visible in the background. "
            "Golden dawn lighting — warm, low sun angle from the right, long shadows. "
            "Do NOT add any other people, animals, or objects. "
            "Do NOT add poker chips, playing cards, gambling items, gold chains. "
            "Do NOT add news desks, microphones, CCTV cameras, or text labels as props. "
            "Do NOT add any text or watermarks."
        ),
        "scene_prompt": (
            "A man in a business suit stands on this gravel road holding a briefcase in one hand and a fishing "
            "rod in the other, looking torn between them. He glances at the briefcase — his face tightens with "
            "stress. He glances at the fishing rod — his face softens into a smile. Back to briefcase — stress. "
            "Back to rod — smile. Three fast glances back and forth, the decision accelerating. "
            "He makes up his mind. He lifts the briefcase high overhead with one arm and hurls it dramatically "
            "over his shoulder — it tumbles through the air and lands in the grass with a heavy thud, papers "
            "exploding out of it and scattering across the ground. He watches the papers fly with zero regret. "
            "Then he reaches up, grabs his necktie, and yanks it off with one sharp pull — whips it away "
            "like a lasso. It flutters to the ground. He kicks off his dress shoes one at a time — each shoe "
            "arcs through the air. He unbuttons his suit jacket, shrugs it off his shoulders, lets it drop "
            "to the gravel behind him. "
            "Now standing in just his dress shirt (untucked, sleeves rolling up) and suit pants, he grips the "
            "fishing rod with both hands, raises it above his head like a trophy, and takes off running down "
            "the road away from camera — barefoot on the gravel, dress shirt billowing, pure unbridled joy on "
            "his face. His run is celebratory, almost skipping, arms pumping, fishing rod bouncing. "
            "Behind him: a trail of discarded corporate life — shoes, jacket, tie, papers blowing in the breeze. "
            "Golden dawn light from the right, long warm shadows stretching across the road. Dust kicks up from "
            "his barefoot steps. The 515 sign glows in the morning light in the background. "
            "Keep the same golden dawn lighting throughout. Do not change lighting or time of day. "
            "Single continuous shot, no cuts. "
            "Filmed on a phone camera, slightly grainy, handheld feel."
        ),
    },
    "cctv_armadillo_concierge": {
        "format": "cctv",
        "title": "Armadillo runs the front desk",
        "plate": "reference_bank/armadillo_desk_start.png",
        "time_of_day": "afternoon",
        "headline": ("Armadillo spotted operating front desk",
                     "at 515 Scenic Cabins on Lake Fork"),
        "clear_instructions": (
            "Grok: Upload plates_signed/plate_0010.jpg (cabin parking/entrance, has 515 sign). Add these items: "
            "1) A wooden crate turned on its side on the porch, acting as a front desk. "
            "A tiny brass bell sits on top. A small handwritten sign says FRONT DESK. "
            "2) BEHIND the crate: ONE armadillo standing on its hind legs wearing a tiny "
            "cowboy hat and a miniature name tag pinned to its shell. "
            "3) IN FRONT of the crate: ONE human man in fishing clothes (vest, hat, boots) "
            "holding a duffel bag, looking down at the armadillo with a bewildered expression. "
            "Only these two characters — one armadillo, one human. No other animals or people. "
            "This is shot from a security camera perspective — wide angle, slightly elevated. "
            "Do NOT add a physical CCTV camera, pole, or label as a prop in the scene. "
            "Do NOT add any text, watermarks, or overlay graphics."
        ),
        "scene_prompt": (
            "An armadillo in a tiny cowboy hat runs the cabin front desk from behind a wooden crate on the porch. "
            "A confused fisherman guest stands in front holding a duffel bag, looking down at the armadillo "
            "with complete bewilderment. The duffel bag strap slips off his shoulder as he stares. "
            "The armadillo reaches one tiny clawed foot up and taps the brass bell on the desk — DING. The bell "
            "vibrates visibly on the wooden crate surface. It looks up at the guest expectantly, its tiny cowboy "
            "hat slightly crooked. The guest just stares. The armadillo taps the bell again, more insistently — "
            "DING DING. It pushes a tiny clipboard toward the guest with both front paws — the clipboard slides "
            "across the crate. It points at the clipboard with one claw. "
            "The guest slowly bends down and picks up the clipboard, his fishing vest crinkling. The armadillo "
            "nods approvingly, reaches under the desk with one armored arm, and produces a tiny room key on a "
            "keychain — holds it up toward the guest with both paws extended overhead, stretching on its "
            "tiptoes, claws clicking on the wooden crate as it reaches. The keychain swings and jingles. "
            "The guest takes the key, still looking confused. The armadillo drops back to all fours — its "
            "armored plates clack together as it lands — scurries out from behind the desk, claws clicking "
            "on the porch boards, and waddles ahead toward the cabin door, looking back over its armored "
            "shoulder to make sure the guest is following. It reaches the door and sits beside it, gesturing "
            "toward the entrance with one paw like a proper bellhop. "
            "The guest follows slowly, looking around to see if he's on a hidden camera. "
            "Bright warm afternoon sunlight on the cabin porch. Shade under the overhang. A slight breeze "
            "shifts the leaves casting dappled light on the concrete. "
            "Keep the same bright daytime lighting throughout. Do not change lighting or time of day. "
            "Single continuous shot, no cuts. "
            "Static security camera angle, slight wide-angle distortion."
        ),
    },
    "cctv_ufo_raccoons": {
        "format": "cctv",
        "title": "UFO abducts the Rowdy Raccoons",
        "plate": "reference_bank/ufo_cabins_start.png",
        "time_of_day": "evening",
        "headline": ("UFO spotted abducting the Rowdy Raccoons",
                     "at 515 Scenic Cabins on Lake Fork"),
        "clear_instructions": (
            "Grok: Upload plates_signed/plate_0080.jpg (has 515 sign pre-composited). "
            "\n\n"
            "ADD A HUGE SILVER FLYING SAUCER in the SKY. "
            "The saucer is the BIGGEST object in the entire image — wider than the boat shed, "
            "wider than any cabin. It takes up the ENTIRE upper third of the frame. "
            "It hovers at treetop height or ABOVE the treetops. "
            "A bright pale blue tractor beam cone of light shines straight down from the "
            "saucer's underside to the grass, illuminating a circle on the ground. "
            "\n\n"
            "Below the beam on the grass, add 3 raccoons — all the same size, all adult, "
            "all chunky. Do NOT make one smaller or bigger than the others. "
            "Three raccoons, not four. Plain wild raccoons, no props. "
            "Raccoon 1 (left): standing, looking up. "
            "Raccoon 2 (center): floating in the beam. "
            "Raccoon 3 (right): clawing at the grass. "
            "\n\n"
            "CRITICAL — DO NOT ADD ANY OF THESE: "
            "No poker chips, playing cards, gambling items, gold chains, sunglasses, "
            "visors, hats, costumes, accessories. No CCTV camera, security camera, "
            "camera pole, camera equipment. No text, labels, watermarks, signs. "
            "\n\n"
            "Evening golden hour lighting — warm, long shadows."
        ),
        "scene_prompt": (
            "A huge silver flying saucer hovers above the grass clearing, pale blue tractor beam cone "
            "shining down. Three raccoons are caught in the beam's pull. "
            "IMPORTANT: Three distinct raccoons, always separate, never merging or overlapping. "
            "Raccoon 1 (lighter grey-brown fur, notched left ear — the leader) stands upright shielding "
            "its eyes, studying the saucer with calm curiosity. It takes one deliberate step into the beam, "
            "testing it. Its fur ripples upward in the beam's energy. It looks back at the other two and "
            "gestures 'come on' with one paw. "
            "Raccoon 2 (darker prominent black mask — the schemer) is already floating two feet off the "
            "ground inside the beam, limbs splayed outward, spinning slowly. It grabs at the air with "
            "its paws, panicked. Its dark mask markings make its wide terrified eyes look enormous. Grass "
            "blades and small leaves float upward around it, caught in the same pull. "
            "Raccoon 3 (oversized bushy striped tail — the hothead) fights the beam. All four claws dug "
            "into the grass, tearing up divots of dirt and roots. Its bushy tail sticks straight out behind "
            "it, horizontal from the upward pull. It snarls at the saucer. The beam intensifies — the "
            "light cone brightens — and Raccoon 3's back legs lift off the ground despite its grip. Its "
            "claws leave four long scratch marks in the dirt as it slides forward. "
            "Raccoon 1 steps fully into the beam and rises slowly, arms crossed, completely unbothered, "
            "rising past the still-panicking Raccoon 2. "
            "Raccoon 3 finally loses its grip — claws rip free from the earth with a spray of dirt — and "
            "it tumbles upward into the beam, flailing and snarling the whole way up. Its bushy tail "
            "puffs out to twice its normal size. "
            "All three float upward toward the saucer's underside hatch. The beam pulses gently. Grass "
            "below is flattened in a perfect circle. Dust and leaves swirl in the displaced air. "
            "Warm evening golden hour light. The tractor beam casts a pale blue glow on the grass and "
            "on the raccoons' fur. Long shadows from the cabins stretch across the clearing. The metal "
            "boat shed reflects a faint blue shimmer from the beam. "
            "Keep the same warm evening lighting throughout. Do not change the time of day. "
            "Single continuous shot, no cuts. "
            "Static security camera angle, slight wide-angle distortion, timestamp overlay."
        ),
    },
}


# ──────────────────────────────────────────────────────────────
# PLATE CATALOG
# ──────────────────────────────────────────────────────────────
PLATE_CATALOG = {
    "plate_0001.jpg": {"name": "Road with boats", "surface": "road_grass"},
    "plate_0005.jpg": {"name": "Marina dock area", "surface": "dock"},
    "plate_0070.jpg": {"name": "Patio with fire pit", "surface": "concrete"},
    "plate_0080.jpg": {"name": "Boat shed with lawn", "surface": "grass"},
    "plate_0100.jpg": {"name": "Deck with picnic tables", "surface": "deck"},
    "plate_0110.jpg": {"name": "515 front wide", "surface": "road_grass"},
    "vertical/plate_0100.jpg": {"name": "Deck with furniture (vertical 9:16)", "surface": "deck"},
    "vertical/plate_0100_clean.jpg": {"name": "Deck cleaned (vertical 9:16)", "surface": "deck"},
}


# ──────────────────────────────────────────────────────────────
# API — fal.ai queue-based calling for Kling V3 Pro
# ──────────────────────────────────────────────────────────────

def _get_fal_key():
    kf = SECRETS / "fal_key"
    if kf.exists():
        return kf.read_text().strip()
    return os.environ.get("FAL_KEY")


def _fal_queue_call(endpoint, data, max_wait=900):
    key = _get_fal_key()
    if not key:
        print("  No fal.ai key. Run: echo 'KEY' > ~/.boss_secrets/fal_key")
        return None

    headers = {
        "Authorization": f"Key {key}",
        "Content-Type": "application/json",
        "User-Agent": "BOSS-515/7.0",
    }

    submit_url = f"https://queue.fal.run/{endpoint}"
    req = urllib.request.Request(submit_url, headers=headers,
                                 data=json.dumps(data).encode(), method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        submit = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  fal.ai submit error {e.code}: {e.read().decode()[:300]}")
        return None
    except Exception as e:
        print(f"  fal.ai submit failed: {e}")
        return None

    request_id = submit.get("request_id")
    if not request_id:
        print(f"  No request_id: {submit}")
        return None
    print(f"  Queued: {request_id[:30]}...")

    status_url = submit.get("status_url",
        f"https://queue.fal.run/{endpoint}/requests/{request_id}/status")
    result_url = submit.get("response_url",
        f"https://queue.fal.run/{endpoint}/requests/{request_id}")

    elapsed = 0
    interval = 15
    while elapsed < max_wait:
        time.sleep(interval)
        elapsed += interval
        try:
            req = urllib.request.Request(status_url, headers={
                "Authorization": f"Key {key}", "User-Agent": "BOSS-515/7.0"})
            resp = urllib.request.urlopen(req, timeout=15)
            st = json.loads(resp.read().decode())
            status = st.get("status", "unknown")
            if status == "COMPLETED":
                print(f"  Completed ({elapsed}s)")
                break
            elif status in ("FAILED", "CANCELLED"):
                print(f"  {status} ({elapsed}s)")
                logs = st.get("logs", [])
                if logs:
                    print(f"  Logs: {logs[-1] if isinstance(logs[-1], str) else json.dumps(logs[-1])[:200]}")
                return None
            else:
                queue_pos = st.get("queue_position", "?")
                print(f"  {status} pos={queue_pos} ({elapsed}s)")
        except Exception as e:
            print(f"  Poll error ({elapsed}s): {e}")
    else:
        print(f"  Timed out after {max_wait}s")
        return None

    try:
        req = urllib.request.Request(result_url, headers={
            "Authorization": f"Key {key}", "User-Agent": "BOSS-515/7.0"})
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  Result fetch error {e.code}: {e.read().decode()[:300]}")
        return None
    except Exception as e:
        print(f"  Result fetch failed: {e}")
        return None


def _upload_to_fal(file_path):
    key = _get_fal_key()
    if not key:
        return None

    with open(file_path, "rb") as f:
        file_data = f.read()

    ext = str(file_path).lower().rsplit(".", 1)[-1]
    content_type = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                    "webp": "image/webp"}.get(ext, "image/jpeg")

    # Try presigned upload
    try:
        req = urllib.request.Request(
            "https://rest.alpha.fal.ai/storage/upload/initiate",
            headers={
                "Authorization": f"Key {key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "BOSS-515/7.0",
            },
            data=json.dumps({
                "content_type": content_type,
                "file_name": Path(file_path).name,
            }).encode(), method="POST")
        resp = urllib.request.urlopen(req, timeout=15)
        upload_info = json.loads(resp.read().decode())

        upload_target = upload_info.get("upload_url") or upload_info.get("presigned_url")
        file_url = upload_info.get("file_url")

        if upload_target:
            put_req = urllib.request.Request(upload_target, data=file_data, method="PUT",
                                             headers={"Content-Type": content_type})
            urllib.request.urlopen(put_req, timeout=60)
            if file_url:
                print(f"  Uploaded plate to fal.ai storage")
                return file_url
    except Exception as e:
        print(f"  Presigned upload failed: {e}")

    # Fallback: base64 data URI
    import base64
    b64 = base64.b64encode(file_data).decode()
    data_uri = f"data:{content_type};base64,{b64}"
    print(f"  Using base64 fallback ({len(b64) // 1024}KB)")
    return data_uri


def _download(url, dest, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=300)
            data = b""
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                data += chunk
            with open(dest, "wb") as f:
                f.write(data)
            return
        except Exception as e:
            if attempt < retries - 1:
                print(f"  Download failed (attempt {attempt+1}): {e}, retrying in 5s...")
                time.sleep(5)
            else:
                raise


# ──────────────────────────────────────────────────────────────
# IDEAS MANAGEMENT
# ──────────────────────────────────────────────────────────────

def _load_ideas():
    return json.loads(IDEAS_FILE.read_text()) if IDEAS_FILE.exists() else {}

def _save_ideas(data):
    IDEAS_FILE.write_text(json.dumps(data, indent=2, default=str) + "\n")

def _get_approved():
    ideas = _load_ideas()
    return [v for v in VIDEO_IDEAS if ideas.get(v, {}).get("status") == "approved"]

def _get_next():
    ideas = _load_ideas()
    for v in VIDEO_IDEAS:
        if ideas.get(v, {}).get("status") == "approved":
            return v
    return None


# ──────────────────────────────────────────────────────────────
# KLING V3 PRO — single-shot image-to-video generation
# ──────────────────────────────────────────────────────────────

def generate_video(idea_id):
    if idea_id not in VIDEO_IDEAS:
        print(f"Unknown idea: {idea_id}")
        return None

    meta = VIDEO_IDEAS[idea_id]
    print(f"\n{'='*60}")
    print(f"[{meta['format'].upper()}] {meta['title']}")
    print(f"  Plate: {meta['plate']} | Duration: 15s | Platform: Kling V3 Pro")
    print(f"{'='*60}")

    plate_path = PLATES_DIR / meta["plate"]
    if not plate_path.exists():
        print(f"  ABORT: Plate not found: {plate_path}")
        return None

    # Upload plate to fal.ai
    print(f"  Uploading plate...")
    plate_url = _upload_to_fal(plate_path)
    if not plate_url:
        print(f"  ABORT: Failed to upload plate")
        return None

    # Enrich prompt with scene context grounding
    enriched_prompt = _enrich_prompt(meta["scene_prompt"], meta)

    # Kling V3 Pro hard limit: 2500 chars. Truncate at last sentence boundary.
    KLING_MAX_PROMPT = 2500
    if len(enriched_prompt) > KLING_MAX_PROMPT:
        truncated = enriched_prompt[:KLING_MAX_PROMPT]
        last_period = truncated.rfind(".")
        if last_period > KLING_MAX_PROMPT // 2:
            truncated = truncated[:last_period + 1]
        enriched_prompt = truncated
        print(f"  Enriched prompt: TRUNCATED to {len(enriched_prompt)} chars (raw: {len(meta['scene_prompt'])})")
    else:
        print(f"  Enriched prompt: {len(enriched_prompt)} chars (raw: {len(meta['scene_prompt'])})")

    # Call Kling V3 Pro image-to-video
    print(f"  Generating 15s video via Kling V3 Pro...")
    result = _fal_queue_call(KLING_ENDPOINT, {
        "image_url": plate_url,
        "prompt": enriched_prompt,
        "negative_prompt": NEGATIVE_PROMPT_FULL,
        "duration": "15",
        "aspect_ratio": "9:16",
        "cfg_scale": 0.7,
    })

    if not result:
        print(f"  Generation failed")
        return None

    # Extract video URL from result
    video_url = None
    video_data = result.get("video")
    if isinstance(video_data, dict):
        video_url = video_data.get("url")
    elif isinstance(video_data, str):
        video_url = video_data

    if not video_url:
        print(f"  No video URL in response. Keys: {list(result.keys())}")
        if result.get("data"):
            d = result["data"]
            if isinstance(d, dict):
                video_url = d.get("video", {}).get("url") if isinstance(d.get("video"), dict) else d.get("video")
        if not video_url:
            print(f"  Response: {json.dumps(result)[:500]}")
            return None

    # Download video
    output_name = f"{meta['format']}_{idea_id.replace(meta['format'] + '_', '', 1)}.mp4"
    output_path = RAW_DIR / output_name
    print(f"  Downloading video...")
    _download(video_url, output_path)
    size_kb = output_path.stat().st_size // 1024
    print(f"  Downloaded: {output_path.name} ({size_kb}KB)")

    # iPhone camera post-processing — masks AI artifacts
    print(f"  Applying phone camera look...")
    apply_phone_camera_look(output_path)

    # CCTV overlay for cctv-format ideas (timestamp, REC indicator)
    if meta["format"] == "cctv":
        print(f"  Adding CCTV overlay...")
        add_cctv_overlay(output_path, idea_id, meta.get("time_of_day", "night"))

    # News overlay on ALL videos — BREAKING NEWS ticker + headline
    print(f"  Adding news overlay...")
    add_news_overlay(output_path, idea_id, meta)

    # Save no-audio backup (for re-timing without re-generating)
    backup_path = BACKUP_DIR / output_path.name
    import shutil
    shutil.copy2(str(output_path), str(backup_path))
    print(f"  Saved no-audio backup for re-timing")

    # Audio sync — analyze ACTUAL video motion, place sounds at real timestamps
    print(f"  Running motion-synced audio (analyzing real video)...")
    synced_spec = sync_audio_to_video(idea_id, output_path)
    if synced_spec and synced_spec.get("layers"):
        AUDIO_SPECS[idea_id] = synced_spec
        missing = check_sfx_availability(idea_id)
        if missing:
            print(f"  WARNING: Missing SFX (skipping those): {', '.join(missing)}")
        print(f"  Mixing {len(synced_spec['layers'])} audio layers (motion-synced)...")
        apply_audio_mix(output_path, idea_id)
    else:
        print(f"  Motion analysis returned no layers — trying fallback...")
        audio_spec = auto_audio_spec(idea_id)
        AUDIO_SPECS[idea_id] = audio_spec
        if audio_spec.get("layers"):
            apply_audio_mix(output_path, idea_id)

    # Print timing map for review
    print_timing_map(idea_id)

    # Quality gate — goes to review/ not ready/
    review_path = REVIEW_DIR / output_path.name
    import shutil as _sh
    _sh.copy2(str(output_path), str(review_path))

    duration = _video_info(output_path)
    size_kb = output_path.stat().st_size // 1024

    # Run automated quality checks
    qc = _quality_check(review_path)

    print(f"\n  {'='*50}")
    print(f"  QUALITY GATE — {meta['title']}")
    print(f"  {'='*50}")
    print(f"  File: {size_kb}KB | Duration: {duration}")
    for check_name, passed, detail in qc:
        icon = "PASS" if passed else "FAIL"
        print(f"  [{icon}] {check_name}: {detail}")

    fails = [c for c in qc if not c[1]]
    if fails:
        print(f"\n  WARNING: {len(fails)} quality check(s) failed")
        print(f"  Video saved to review/ — inspect before approving")
    else:
        print(f"\n  All quality checks passed")

    print(f"\n  Video in REVIEW: {review_path.name}")
    print(f"  To approve:  python3 515_video_gen.py approve-video {idea_id}")
    print(f"  To reject:   python3 515_video_gen.py reject-video {idea_id}")

    _notify(f"515 video ready for review: {meta['title']} ({duration}) — {len(fails)} QC fails")
    subprocess.run(["open", str(review_path)], check=False)

    # Update ideas JSON
    ideas = _load_ideas()
    ideas[idea_id] = {
        "status": "review",
        "generated_at": datetime.now(CT).isoformat(),
        "video_path": str(output_path),
        "review_path": str(review_path),
        "size_kb": size_kb,
        "duration": duration,
        "pipeline": "kling_v3_pro",
        "qc_fails": len(fails),
    }
    _save_ideas(ideas)
    return output_path


# ──────────────────────────────────────────────────────────────
# PHONE CAMERA POST-PROCESSING — masks AI look
# Subtle grain, slight softening, minor color shift.
# Does NOT change the content, just the rendering quality.
# ──────────────────────────────────────────────────────────────

def apply_phone_camera_look(video_path):
    output = video_path.parent / f"phone_{video_path.name}"
    filt = (
        "noise=c0s=8:c0f=t,"
        "unsharp=3:3:-0.5:3:3:-0.5,"
        "eq=saturation=0.92:contrast=1.03:brightness=0.01,"
        "scale=1080:1920:flags=lanczos"
    )
    cmd = [
        FFMPEG, '-y', '-i', str(video_path),
        '-vf', filt,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
        '-pix_fmt', 'yuv420p', '-an',
        str(output)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode == 0 and output.exists():
        video_path.unlink()
        output.rename(video_path)
        return True
    print(f"  Phone camera look failed: {r.stderr[-200:]}")
    return False


# ──────────────────────────────────────────────────────────────
# AUDIO MIX — layered SFX with realistic phone mic simulation
# in_scene sounds get low-pass filter (phone mic cutoff ~12kHz)
# overlay sounds (news sting) stay clean
# ──────────────────────────────────────────────────────────────

def apply_audio_mix(video_path, idea_id):
    spec = AUDIO_SPECS.get(idea_id)
    if not spec:
        return False

    layers = spec.get("layers", [])
    if not layers:
        return False

    video_dur_str = _video_info(video_path)
    try:
        parts = video_dur_str.split(":")
        video_dur = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    except Exception:
        video_dur = 15.0

    inputs = ["-i", str(video_path)]
    filter_parts = []
    mix_inputs = []
    input_idx = 1

    for i, layer in enumerate(layers):
        sfx_path = SFX_DIR / layer["file"]
        if not sfx_path.exists():
            print(f"  WARNING: SFX missing: {sfx_path.name}")
            continue

        inputs.extend(["-i", str(sfx_path)])
        vol = layer["volume_db"]
        start = layer["start"]
        in_scene = layer.get("in_scene", True)
        loop = layer.get("loop", False)

        chain = f"[{input_idx}:a]"
        filters = []

        if loop:
            filters.append(f"aloop=loop=-1:size=2e+09")
            filters.append(f"atrim=0:{video_dur}")

        if start > 0:
            filters.append(f"adelay={int(start * 1000)}|{int(start * 1000)}")

        filters.append(f"volume={vol}dB")

        if in_scene:
            filters.append("lowpass=f=12000")
            filters.append("highpass=f=80")

        filters.append(f"apad=whole_dur={video_dur}")
        filters.append(f"atrim=0:{video_dur}")

        filter_label = f"[a{i}]"
        filter_parts.append(f"{chain}{','.join(filters)}{filter_label}")
        mix_inputs.append(f"[a{i}]")
        input_idx += 1

    if not mix_inputs:
        print(f"  No valid audio layers")
        return False

    n = len(mix_inputs)
    mix_str = "".join(mix_inputs)
    filter_parts.append(f"{mix_str}amix=inputs={n}:duration=first:dropout_transition=0[mixed]")
    filter_parts.append(f"[mixed]alimiter=limit=0.95[aout]")

    full_filter = ";".join(filter_parts)
    output = video_path.parent / f"audio_{video_path.name}"

    cmd = [
        FFMPEG, "-y",
        *inputs,
        "-filter_complex", full_filter,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(output),
    ]

    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode == 0 and output.exists():
        video_path.unlink()
        output.rename(video_path)
        print(f"  Audio mix applied: {n} layers")
        return True

    print(f"  Audio mix failed: {r.stderr[-400:]}")
    return False


# ──────────────────────────────────────────────────────────────
# CCTV OVERLAY — static camera, timestamp, REC dot
# ──────────────────────────────────────────────────────────────

def add_cctv_overlay(video_path, idea_id, time_of_day="night"):
    meta = VIDEO_IDEAS.get(idea_id, {})
    today = datetime.now(CT).strftime("%m/%d/%Y")
    fake_times = {"night": "02:47:13", "dawn": "05:32:41", "evening": "19:14:22",
                  "afternoon": "14:23:07", "sunset": "19:45:33"}
    fake_time = fake_times.get(time_of_day, "03:15:42")
    cam_label = "CAM 03 — DECK" if "deck" in meta.get("plate", "") else "CAM 01 — PROPERTY"

    font = "/System/Library/Fonts/Menlo.ttc"
    output = video_path.parent / f"cctv_{video_path.name}"

    ts_escaped = fake_time.replace(":", "\\:")
    filt = (
        f"drawtext=fontfile='{font}':text='515 SCENIC CABINS':"
        f"fontsize=18:fontcolor=white:x=20:y=20:borderw=1:bordercolor=black,"
        f"drawtext=fontfile='{font}':text='{cam_label}':"
        f"fontsize=14:fontcolor=white:x=20:y=46:borderw=1:bordercolor=black,"
        f"drawtext=fontfile='{font}':text='{today}  {ts_escaped}':"
        f"fontsize=16:fontcolor=white:x=w-tw-20:y=20:borderw=1:bordercolor=black,"
        f"drawtext=fontfile='{font}':text='* REC':"
        f"fontsize=14:fontcolor=red:x=w-tw-20:y=46:borderw=1:bordercolor=black"
    )

    audio_args = ['-c:a', 'copy'] if _has_audio(video_path) else ['-an']
    cmd = [FFMPEG, '-y', '-i', str(video_path), '-vf', filt,
           '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
           '-pix_fmt', 'yuv420p', *audio_args, str(output)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if r.returncode == 0 and output.exists():
        video_path.unlink()
        output.rename(video_path)
        return True

    print(f"  CCTV overlay failed: {r.stderr[-300:]}")
    return False


# ──────────────────────────────────────────────────────────────
# NEWS OVERLAY — FIXED: ticker matches headline box width, text centered
# ──────────────────────────────────────────────────────────────

def _auto_fontsize(lines, font_path, max_width, max_fs=100, min_fs=36):
    from PIL import ImageFont, Image, ImageDraw
    try:
        img = Image.new('RGB', (max_width + 100, 400), 'white')
        draw = ImageDraw.Draw(img)
        for fs in range(max_fs, min_fs - 1, -1):
            font = ImageFont.truetype(font_path, fs)
            fits = True
            heights = []
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                tw = bbox[2] - bbox[0]
                if tw > max_width:
                    fits = False
                    break
                heights.append(bbox[3] - bbox[1])
            if fits:
                return fs, heights
        font = ImageFont.truetype(font_path, min_fs)
        heights = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            heights.append(bbox[3] - bbox[1])
        return min_fs, heights
    except Exception:
        return 56, [48, 44]


def add_news_overlay(video_path, idea_id, meta):
    from PIL import Image, ImageDraw, ImageFont

    line1, line2 = meta.get("headline", ("Unusual activity reported",
                                          "at 515 Scenic Cabins on Lake Fork"))

    W, H = 1080, 1920
    bold_font = "/System/Library/Fonts/Supplemental/Impact.ttf"

    CARD_W = int(W * 0.88)
    CARD_X = (W - CARD_W) // 2

    text_max_w = int(CARD_W * 0.88)
    headline_fs, text_heights = _auto_fontsize([line1, line2], bold_font, max_width=text_max_w)
    th1 = text_heights[0] if len(text_heights) > 0 else int(headline_fs * 0.88)
    th2 = text_heights[1] if len(text_heights) > 1 else int(headline_fs * 0.82)

    TICKER_H = 58
    CORNER_R = 16

    line_gap = max(int(headline_fs * 0.12), 5)
    total_text_h = th1 + line_gap + th2
    pad_top = int(headline_fs * 0.38)
    pad_bot = int(headline_fs * 0.30)
    white_h = pad_top + total_text_h + pad_bot

    card_bottom = int(H * 0.96)
    white_top = card_bottom - white_h
    ticker_top = white_top - TICKER_H

    overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))

    # Ticker bar — SAME WIDTH as headline card, rounded top corners, NO text (text scrolls via FFmpeg)
    ticker = Image.new('RGBA', (CARD_W, TICKER_H), (220, 31, 32, 242))
    ticker_mask = Image.new('L', (CARD_W, TICKER_H), 0)
    ticker_mask_draw = ImageDraw.Draw(ticker_mask)
    ticker_mask_draw.rounded_rectangle([0, 0, CARD_W - 1, TICKER_H + CORNER_R],
                                        radius=CORNER_R, fill=255)
    ticker_transparent = Image.new('RGBA', (CARD_W, TICKER_H), (0, 0, 0, 0))
    ticker_masked = Image.composite(ticker, ticker_transparent, ticker_mask)
    overlay.paste(ticker_masked, (CARD_X, ticker_top), ticker_masked)

    # White headline card with rounded bottom corners
    wb = Image.new('RGBA', (CARD_W, white_h), (255, 255, 255, 250))
    wb_draw = ImageDraw.Draw(wb)

    font = ImageFont.truetype(bold_font, headline_fs)

    bbox1 = wb_draw.textbbox((0, 0), line1, font=font)
    tw1 = bbox1[2] - bbox1[0]
    x1 = (CARD_W - tw1) // 2 - bbox1[0]
    wb_draw.text((x1, pad_top - bbox1[1]), line1, fill=(0, 0, 0, 255), font=font)

    bbox2 = wb_draw.textbbox((0, 0), line2, font=font)
    tw2 = bbox2[2] - bbox2[0]
    x2 = (CARD_W - tw2) // 2 - bbox2[0]
    wb_draw.text((x2, pad_top + th1 + line_gap - bbox2[1]), line2, fill=(0, 0, 0, 255), font=font)

    card_mask = Image.new('L', (CARD_W, white_h), 0)
    card_mask_draw = ImageDraw.Draw(card_mask)
    card_mask_draw.rounded_rectangle([0, -CORNER_R, CARD_W - 1, white_h - 1],
                                      radius=CORNER_R, fill=255)
    transparent = Image.new('RGBA', (CARD_W, white_h), (0, 0, 0, 0))
    wb_masked = Image.composite(wb, transparent, card_mask)

    overlay.paste(wb_masked, (CARD_X, white_top), wb_masked)

    overlay_png = video_path.parent / f"overlay_{video_path.stem}.png"
    overlay.save(str(overlay_png), 'PNG')

    # Scrolling ticker: crop ticker area → draw scrolling text → overlay back
    ticker_text = "   BREAKING NEWS   " * 15
    ticker_text = ticker_text.replace("'", "\\'")
    scroll_speed = 80
    ticker_fs_px = max(int(TICKER_H * 0.44), 18)

    has_audio = _has_audio(video_path)
    audio_map = ['-map', '0:a', '-c:a', 'copy'] if has_audio else []

    output = video_path.parent / f"news_{video_path.name}"
    fc = (
        f"[0:v][1:v]overlay=0:0[base];"
        f"[base]split[b1][b2];"
        f"[b1]crop={CARD_W}:{TICKER_H}:{CARD_X}:{ticker_top}[tcrop];"
        f"[tcrop]drawtext=fontfile='{bold_font}':"
        f"text='{ticker_text}':"
        f"fontsize={ticker_fs_px}:fontcolor=white:"
        f"x='t*{scroll_speed}-tw+w':"
        f"y='(h-th)/2'[ttext];"
        f"[b2][ttext]overlay=x={CARD_X}:y={ticker_top}[out]"
    )

    cmd = [
        FFMPEG, '-y',
        '-i', str(video_path),
        '-i', str(overlay_png),
        '-filter_complex', fc,
        '-map', '[out]',
        *audio_map,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-pix_fmt', 'yuv420p',
        *(['-an'] if not has_audio else []),
        str(output)
    ]

    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    overlay_png.unlink(missing_ok=True)

    if r.returncode == 0 and output.exists():
        video_path.unlink()
        output.rename(video_path)
        return True

    print(f"  News overlay failed: {r.stderr[-400:]}")
    return False


# ──────────────────────────────────────────────────────────────
# UTILS
# ──────────────────────────────────────────────────────────────

def _quality_check(video_path):
    checks = []

    # 1. File size — too small means corrupted/empty
    size_kb = video_path.stat().st_size // 1024
    if size_kb < 500:
        checks.append(("File size", False, f"{size_kb}KB — suspiciously small, likely corrupted"))
    elif size_kb < 2000:
        checks.append(("File size", False, f"{size_kb}KB — very small for 15s video, check quality"))
    else:
        checks.append(("File size", True, f"{size_kb}KB"))

    # 2. Duration — should be ~15s
    dur_str = _video_info(video_path)
    try:
        parts = dur_str.split(":")
        dur_sec = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        if dur_sec < 10:
            checks.append(("Duration", False, f"{dur_sec:.1f}s — too short, expected ~15s"))
        elif dur_sec > 20:
            checks.append(("Duration", False, f"{dur_sec:.1f}s — too long, expected ~15s"))
        else:
            checks.append(("Duration", True, f"{dur_sec:.1f}s"))
    except Exception:
        checks.append(("Duration", False, f"Could not parse: {dur_str}"))

    # 3. Resolution — should be 1080x1920
    try:
        r = subprocess.run(
            [FFMPEG, '-i', str(video_path)],
            capture_output=True, text=True, timeout=10
        )
        res_match = re.search(r'(\d{3,4})x(\d{3,4})', r.stderr)
        if res_match:
            w, h = int(res_match.group(1)), int(res_match.group(2))
            if w == 1080 and h == 1920:
                checks.append(("Resolution", True, f"{w}x{h} (9:16)"))
            else:
                checks.append(("Resolution", False, f"{w}x{h} — expected 1080x1920"))
        else:
            checks.append(("Resolution", False, "Could not detect resolution"))
    except Exception:
        checks.append(("Resolution", False, "FFmpeg probe failed"))

    # 4. Has audio — should have audio after the mix
    if _has_audio(video_path):
        checks.append(("Audio", True, "Audio track present"))
    else:
        checks.append(("Audio", False, "No audio track — audio mix may have failed"))

    # 5. Frame motion check — extract first and last frame, compare
    try:
        frame_first = video_path.parent / f"_qc_first_{video_path.stem}.png"
        frame_last = video_path.parent / f"_qc_last_{video_path.stem}.png"
        subprocess.run(
            [FFMPEG, '-y', '-i', str(video_path), '-vframes', '1', '-q:v', '2', str(frame_first)],
            capture_output=True, timeout=15
        )
        subprocess.run(
            [FFMPEG, '-y', '-sseof', '-1', '-i', str(video_path), '-vframes', '1', '-q:v', '2', str(frame_last)],
            capture_output=True, timeout=15
        )
        if frame_first.exists() and frame_last.exists():
            from PIL import Image
            import numpy as np
            img1 = np.array(Image.open(frame_first).convert('L').resize((108, 192)))
            img2 = np.array(Image.open(frame_last).convert('L').resize((108, 192)))
            diff = np.mean(np.abs(img1.astype(float) - img2.astype(float)))
            frame_first.unlink(missing_ok=True)
            frame_last.unlink(missing_ok=True)
            if diff < 5.0:
                checks.append(("Motion", False, f"Pixel diff {diff:.1f} — video looks STATIC, nothing happening"))
            elif diff < 20.0:
                checks.append(("Motion", False, f"Pixel diff {diff:.1f} — minimal motion, likely AI slop"))
            else:
                checks.append(("Motion", True, f"Pixel diff {diff:.1f} — visible motion detected"))
        else:
            checks.append(("Motion", False, "Could not extract frames for comparison"))
            frame_first.unlink(missing_ok=True)
            frame_last.unlink(missing_ok=True)
    except Exception as e:
        checks.append(("Motion", False, f"Frame analysis failed: {e}"))

    return checks


def _has_audio(path):
    try:
        r = subprocess.run([FFMPEG, '-i', str(path)], capture_output=True, text=True, timeout=10)
        return 'Audio:' in r.stderr
    except Exception:
        return False


def _video_info(path):
    try:
        r = subprocess.run([FFMPEG, '-i', str(path)], capture_output=True, text=True, timeout=10)
        m = re.search(r'Duration: (\d+:\d+:\d+\.\d+)', r.stderr)
        return m.group(1) if m else "?"
    except Exception:
        return "?"


def _notify(msg):
    try:
        req = urllib.request.Request("https://ntfy.sh/bossai-bostonrossall-alerts",
                                     data=msg.encode(), method="POST",
                                     headers={"User-Agent": "BOSS-515/7.0"})
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

def cmd_status():
    key = _get_fal_key()
    ideas = _load_ideas()
    approved = _get_approved()
    generated = [k for k, v in ideas.items() if v.get("status") == "generated"]

    print(f"\n515 Video Generator v7 — Kling V3 Pro (Single-Shot Image-to-Video)")
    print(f"  fal.ai: {'READY' if key else 'NOT SET UP'}")
    if not key:
        print(f"    echo 'KEY' > ~/.boss_secrets/fal_key")
    print(f"  Platform: Kling V3 Pro via fal.ai (~$1.68/video)")
    print(f"  Duration: 15s single-shot | Format: 9:16 vertical")
    print(f"  Ideas: {len(VIDEO_IDEAS)} | Approved: {len(approved)} | Generated: {len(generated)}")
    print(f"  Plates: {len(list(PLATES_DIR.glob('*.jpg')))} + {len(list((PLATES_DIR / 'vertical').glob('*.jpg'))) if (PLATES_DIR / 'vertical').exists() else 0} vertical")

    if approved:
        print(f"\n  Queue:")
        for a in approved:
            m = VIDEO_IDEAS.get(a, {})
            print(f"    [{m.get('format', '?').upper():<6}] {m.get('title', a)}")

    if key:
        print(f"\n  Testing key...")
        try:
            req = urllib.request.Request("https://fal.run/fal-ai/fast-sdxl",
                headers={"Authorization": f"Key {key}", "Content-Type": "application/json",
                         "User-Agent": "BOSS-515/7.0"},
                data=json.dumps({"prompt": "test", "num_images": 0}).encode(), method="POST")
            urllib.request.urlopen(req, timeout=10)
            print(f"  fal.ai: CONNECTED")
        except urllib.error.HTTPError:
            print(f"  fal.ai: CONNECTED")
        except Exception:
            print(f"  fal.ai: KEY SAVED")


def cmd_list():
    ideas = _load_ideas()
    print(f"\n515 Ideas ({len(VIDEO_IDEAS)})")
    print("-" * 70)
    for vid, meta in VIDEO_IDEAS.items():
        st = ideas.get(vid, {}).get("status", "new")
        mk = {"new": "  ", "approved": "Y ", "rejected": "X ", "generated": "OK"}.get(st, "? ")
        print(f"  [{mk}] [{meta['format']:<6}] {meta['title']:<35} {meta['plate']}")


def cmd_check(idea_id):
    if idea_id not in VIDEO_IDEAS:
        print(f"Unknown idea: {idea_id}")
        print(f"Available: {', '.join(VIDEO_IDEAS.keys())}")
        return

    meta = VIDEO_IDEAS[idea_id]
    plate_path = PLATES_DIR / meta["plate"]

    print(f"\n{'='*60}")
    print(f"OBSTRUCTION CHECK: {meta['title']}")
    print(f"{'='*60}")
    print(f"  Plate: {meta['plate']}")
    print(f"  Format: {meta['format']}")
    print(f"  Scene: {meta['scene_prompt'][:120]}...")
    print(f"\n  CLEAR THESE OBSTRUCTIONS:")
    print(f"  {meta.get('clear_instructions', 'Check the plate for any items that would clash with the AI-generated scene.')}")

    if plate_path.exists():
        print(f"\n  Opening plate photo...")
        subprocess.run(["open", str(plate_path)])
    else:
        print(f"\n  WARNING: Plate not found at {plate_path}")
        print(f"  Take a vertical 9:16 photo of the location and save it there.")

    print(f"\n  After clearing obstructions:")
    print(f"    1. Take a new photo of the cleared area (vertical 9:16)")
    print(f"    2. Save it to: {plate_path}")
    print(f"    3. Run: python3 515_video_gen.py generate --id {idea_id}")


def cmd_generate(all_mode=False, specific_id=None):
    if not _get_fal_key():
        print("No key. Run: echo 'KEY' > ~/.boss_secrets/fal_key")
        return

    if specific_id:
        targets = [specific_id] if specific_id in VIDEO_IDEAS else []
        if not targets:
            print(f"Unknown idea: {specific_id}")
            print(f"Available: {', '.join(VIDEO_IDEAS.keys())}")
            return
    elif all_mode:
        targets = _get_approved()
    else:
        nxt = _get_next()
        targets = [nxt] if nxt else []

    if not targets:
        print("Nothing to generate. Approve ideas on the dashboard first.")
        return

    print(f"Generating {len(targets)} video(s)...\n")
    done = 0
    for i, vid in enumerate(targets):
        if i > 0:
            time.sleep(5)
        if generate_video(vid):
            done += 1

    print(f"\n{'='*60}")
    print(f"Done: {done}/{len(targets)} videos")
    print(f"{'='*60}")


def cmd_daily():
    nxt = _get_next()
    if nxt and _get_fal_key():
        generate_video(nxt)
    elif not nxt:
        print("No approved ideas in queue.")


def cmd_approve(idea_id):
    if idea_id not in VIDEO_IDEAS:
        print(f"Unknown: {idea_id}")
        return
    ideas = _load_ideas()
    ideas[idea_id] = {"status": "approved", "votedAt": datetime.now(CT).isoformat()}
    _save_ideas(ideas)
    print(f"Approved: {VIDEO_IDEAS[idea_id]['title']}")


def cmd_plates():
    print(f"\nPlate Catalog ({len(PLATE_CATALOG)} plates)")
    print("-" * 60)
    for name, info in sorted(PLATE_CATALOG.items()):
        print(f"  {name:<30} {info['name']}")


def cmd_produce(idea_id):
    if idea_id not in VIDEO_IDEAS:
        print(f"Unknown idea: {idea_id}")
        print(f"Available: {', '.join(VIDEO_IDEAS.keys())}")
        return

    meta = VIDEO_IDEAS[idea_id]
    plate_path = PLATES_DIR / meta["plate"]
    if not plate_path.exists():
        print(f"ABORT: Plate not found: {plate_path}")
        return

    # Plate rotation check — max 1 use per plate per week
    plate_base = Path(meta["plate"]).stem
    if not check_plate_available(plate_base):
        last = plate_last_used(plate_base)
        print(f"BLOCKED: Plate '{plate_base}' was used on {last}")
        print(f"  Each plate can only be used once per {PLATE_COOLDOWN_DAYS} days")
        print(f"  Pick a different idea that uses a different plate")
        return

    if not _get_fal_key():
        print("No key. Run: echo 'KEY' > ~/.boss_secrets/fal_key")
        return

    # Pre-flight: check SFX availability
    spec = AUDIO_SPECS.get(idea_id) or auto_audio_spec(idea_id)
    missing = check_sfx_availability(idea_id)
    print(f"\n{'='*60}")
    print(f"PRODUCING: {meta['title']}")
    print(f"{'='*60}")
    print(f"  Format: {meta['format']} | Plate: {meta['plate']}")
    print(f"  Audio: pre-gen estimate (will re-sync to actual video after generation)")
    if missing:
        print(f"  WARNING: Missing SFX: {', '.join(missing)}")
        print(f"  (will generate without those sounds)")

    # Show pre-gen audio plan (estimate only — real sync happens after generation)
    print(f"\n  PRE-GEN AUDIO PLAN (estimate — will be replaced by motion-synced timing):")
    print_timing_map(idea_id)

    # Generate
    result = generate_video(idea_id)
    if result:
        # Record plate usage for rotation tracking
        _record_plate_use(plate_base)

        ready_path = REVIEW_DIR / result.name
        print(f"\n  IN REVIEW: {ready_path}")
        print(f"  Backup: {BACKUP_DIR / result.name}")
        print(f"\n  Audio was synced to actual video motion — timestamps are exact.")
        print(f"  To fine-tune:  python3 515_video_gen.py retime {idea_id} <layer#>=<seconds>")
        print(f"  To approve:    python3 515_video_gen.py approve-video {idea_id}")
        print(f"  To reject:     python3 515_video_gen.py reject-video {idea_id}")


def cmd_retime(idea_id, adjustments):
    if idea_id not in VIDEO_IDEAS:
        print(f"Unknown idea: {idea_id}")
        return

    meta = VIDEO_IDEAS[idea_id]
    output_name = f"{meta['format']}_{idea_id.replace(meta['format'] + '_', '', 1)}.mp4"
    backup_path = BACKUP_DIR / output_name

    if not backup_path.exists():
        print(f"No backup found at {backup_path}")
        print(f"Run 'produce' first to generate a video with a backup.")
        return

    spec = AUDIO_SPECS.get(idea_id)
    if not spec:
        spec = auto_audio_spec(idea_id)
        AUDIO_SPECS[idea_id] = spec

    if not adjustments:
        print(f"\nCurrent timing for: {meta['title']}")
        print_timing_map(idea_id)
        return

    # Parse adjustments: "2=6.5 4=9.0" → {2: 6.5, 4: 9.0}
    for adj in adjustments:
        if "=" not in adj:
            print(f"  Invalid adjustment: {adj} (use format: <layer#>=<seconds>)")
            continue
        parts = adj.split("=", 1)
        try:
            layer_idx = int(parts[0])
            new_start = float(parts[1])
        except ValueError:
            print(f"  Invalid adjustment: {adj}")
            continue

        if layer_idx < 0 or layer_idx >= len(spec["layers"]):
            print(f"  Layer {layer_idx} out of range (0-{len(spec['layers'])-1})")
            continue

        old_start = spec["layers"][layer_idx]["start"]
        spec["layers"][layer_idx]["start"] = new_start
        fname = spec["layers"][layer_idx]["file"]
        print(f"  Layer {layer_idx} ({fname}): {old_start}s -> {new_start}s")

    AUDIO_SPECS[idea_id] = spec

    # Re-apply audio from the clean backup
    import shutil
    output_path = RAW_DIR / output_name
    shutil.copy2(str(backup_path), str(output_path))

    print(f"\n  Re-mixing audio from backup...")
    result = apply_audio_mix(output_path, idea_id)
    if not result:
        print(f"  Audio re-mix FAILED")
        return

    # Copy to ready
    ready_path = READY_DIR / output_name
    shutil.copy2(str(output_path), str(ready_path))

    print_timing_map(idea_id)
    print(f"\n  DONE: {ready_path}")
    subprocess.run(["open", str(ready_path)])


def cmd_sfx():
    print(f"\nSFX Library ({SFX_DIR})")
    print("-" * 60)
    sfx_files = sorted(SFX_DIR.glob("*.mp3"))
    if not sfx_files:
        print("  No SFX files found")
        return

    for f in sfx_files:
        size_kb = f.stat().st_size // 1024
        dur = "?"
        try:
            r = subprocess.run([FFMPEG, '-i', str(f)], capture_output=True, text=True, timeout=5)
            m = re.search(r'Duration: (\d+:\d+:\d+\.\d+)', r.stderr)
            if m:
                dur = m.group(1)
        except Exception:
            pass
        print(f"  {f.name:<30} {size_kb:>5}KB  {dur}")

    # Check what's needed vs available
    all_needed = set()
    for vid in VIDEO_IDEAS:
        spec = AUDIO_SPECS.get(vid) or auto_audio_spec(vid)
        for layer in spec.get("layers", []):
            all_needed.add(layer["file"])

    available = {f.name for f in sfx_files}
    missing = all_needed - available
    if missing:
        print(f"\n  MISSING ({len(missing)} needed for full coverage):")
        for m in sorted(missing):
            print(f"    {m}")
    else:
        print(f"\n  All needed SFX available")


def cmd_pipeline():
    ready_videos = sorted(READY_DIR.glob("*.mp4"))
    ideas = _load_ideas()

    # Categorize all ideas
    producible = []
    needs_frame = []
    already_done = []

    for vid, meta in VIDEO_IDEAS.items():
        plate_path = PLATES_DIR / meta["plate"]
        output_name = f"{meta['format']}_{vid.replace(meta['format'] + '_', '', 1)}.mp4"
        ready_path = READY_DIR / output_name

        if ready_path.exists():
            already_done.append((vid, meta, ready_path))
        elif plate_path.exists():
            producible.append((vid, meta))
        else:
            needs_frame.append((vid, meta))

    # Count only valid ready videos (from current ideas, not dead leftovers)
    valid_ready = [v for v in ready_videos if any(
        v.name == f"{m['format']}_{vid.replace(m['format'] + '_', '', 1)}.mp4"
        for vid, m in VIDEO_IDEAS.items()
    )]
    dead_ready = [v for v in ready_videos if v not in valid_ready]

    pipeline_depth = len(valid_ready)
    target = 7

    print(f"\n{'='*60}")
    print(f"515 VIDEO PIPELINE")
    print(f"{'='*60}")
    print(f"  Pipeline depth: {pipeline_depth}/{target} {'FULL' if pipeline_depth >= target else 'NEEDS ' + str(target - pipeline_depth) + ' MORE'}")
    print()

    if valid_ready:
        print(f"  READY TO POST ({len(valid_ready)}):")
        for v in valid_ready:
            size_mb = v.stat().st_size / (1024 * 1024)
            print(f"    {v.name:<45} {size_mb:.1f}MB")
    else:
        print(f"  READY TO POST: none")

    print()
    if producible:
        print(f"  PRODUCIBLE NOW — have starting frame ({len(producible)}):")
        for vid, meta in producible:
            print(f"    {vid:<35} {meta['title']}")
        print(f"\n  Run: python3 515_video_gen.py batch")
    else:
        print(f"  PRODUCIBLE NOW: none (all ideas need Grok starting frames)")

    if needs_frame:
        print(f"\n  NEED GROK STARTING FRAME ({len(needs_frame)}):")
        for vid, meta in needs_frame:
            print(f"    {vid:<35} {meta['title']}")
            ci = meta.get('clear_instructions', '')
            if ci:
                first_line = ci[:120] + ('...' if len(ci) > 120 else '')
                print(f"      {first_line}")

    if dead_ready:
        print(f"\n  DEAD VIDEOS in ready/ ({len(dead_ready)}) — run 'clean' to remove:")
        for v in dead_ready:
            print(f"    {v.name}")

    if pipeline_depth < target:
        deficit = target - pipeline_depth
        can_produce = len(producible)
        if can_produce >= deficit:
            print(f"\n  ACTION: Run 'batch' to produce {deficit} videos and fill the pipeline")
        else:
            still_need = deficit - can_produce
            print(f"\n  ACTION: Can produce {can_produce} now. Need {still_need} more Grok starting frames from Boston.")
            if needs_frame:
                print(f"  NEXT FRAMES NEEDED:")
                for vid, meta in needs_frame[:still_need]:
                    ci = meta.get('clear_instructions', 'See script for details')
                    print(f"\n  [{vid}] {meta['title']}")
                    print(f"  {ci}")

    # Plate rotation status
    all_plates = set()
    for vid, meta in VIDEO_IDEAS.items():
        all_plates.add(Path(meta["plate"]).stem)
    usage = _load_plate_usage()
    today = datetime.now(CT)
    available_plates = []
    cooling_plates = []
    for p in sorted(all_plates):
        if check_plate_available(p):
            available_plates.append(p)
        else:
            last = plate_last_used(p)
            cooling_plates.append((p, last))

    if cooling_plates:
        print(f"\n  PLATE ROTATION ({PLATE_COOLDOWN_DAYS}-day cooldown):")
        for p, last in cooling_plates:
            print(f"    [{p}] last used {last} — cooling down")
        print(f"    {len(available_plates)} plates available, {len(cooling_plates)} on cooldown")

    # Balance check
    key = _get_fal_key()
    if key:
        cost_to_fill = max(0, target - pipeline_depth) * 1.68
        if cost_to_fill > 0:
            print(f"\n  Estimated cost to fill pipeline: ~${cost_to_fill:.2f}")


def cmd_batch():
    if not _get_fal_key():
        print("No key. Run: echo 'KEY' > ~/.boss_secrets/fal_key")
        return

    producible = []
    skipped_cooldown = []
    for vid, meta in VIDEO_IDEAS.items():
        plate_path = PLATES_DIR / meta["plate"]
        output_name = f"{meta['format']}_{vid.replace(meta['format'] + '_', '', 1)}.mp4"
        ready_path = READY_DIR / output_name
        if plate_path.exists() and not ready_path.exists():
            plate_base = Path(meta["plate"]).stem
            if check_plate_available(plate_base):
                producible.append(vid)
            else:
                skipped_cooldown.append((vid, plate_base))

    if skipped_cooldown:
        print(f"\n  Skipping {len(skipped_cooldown)} ideas (plate on cooldown):")
        for vid, plate in skipped_cooldown:
            print(f"    {vid} — plate '{plate}' used within last {PLATE_COOLDOWN_DAYS} days")

    if not producible:
        print("Nothing to produce. All eligible ideas either done or plates on cooldown.")
        return

    print(f"\nBatch producing {len(producible)} video(s)...")
    print(f"  Estimated cost: ~${len(producible) * 1.68:.2f}")
    print(f"  Estimated time: ~{len(producible) * 10}-{len(producible) * 15} minutes")
    print()

    done = 0
    failed = []
    for i, vid in enumerate(producible):
        print(f"\n[{i+1}/{len(producible)}] {VIDEO_IDEAS[vid]['title']}")
        try:
            result = generate_video(vid)
            if result:
                done += 1
            else:
                failed.append(vid)
        except Exception as e:
            print(f"  ERROR: {e}")
            failed.append(vid)

        if i < len(producible) - 1:
            time.sleep(3)

    print(f"\n{'='*60}")
    print(f"BATCH COMPLETE: {done}/{len(producible)} videos produced")
    if failed:
        print(f"  Failed: {', '.join(failed)}")
    print(f"{'='*60}")

    # Pipeline status after batch
    ready_count = len(list(READY_DIR.glob("*.mp4")))
    if ready_count < 7:
        _notify(f"515 pipeline at {ready_count}/7 videos after batch. Need more Grok frames.")
    else:
        _notify(f"515 pipeline FULL: {ready_count} videos ready to post.")


def cmd_clean():
    ready_videos = sorted(READY_DIR.glob("*.mp4"))
    valid_names = set()
    for vid, meta in VIDEO_IDEAS.items():
        output_name = f"{meta['format']}_{vid.replace(meta['format'] + '_', '', 1)}.mp4"
        valid_names.add(output_name)
        valid_names.add(f"news_{output_name}")
        valid_names.add(f"cctv_{output_name}")

    dead = [v for v in ready_videos if v.name not in valid_names]
    if not dead:
        print("No dead videos in ready/. All clean.")
        return

    print(f"\nRemoving {len(dead)} dead video(s) from ready/:")
    for v in dead:
        size_mb = v.stat().st_size / (1024 * 1024)
        print(f"  {v.name} ({size_mb:.1f}MB)")
        v.unlink()
    print(f"  Done. Freed {sum(v.stat().st_size for v in dead if v.exists()) / (1024*1024):.1f}MB" if False else "  Done.")


def cmd_test_overlay(idea_id):
    if idea_id not in VIDEO_IDEAS:
        print(f"Unknown idea: {idea_id}")
        return

    meta = VIDEO_IDEAS[idea_id]
    output_name = f"{meta['format']}_{idea_id.replace(meta['format'] + '_', '', 1)}.mp4"

    # Try backup first, then ready, then raw
    source = None
    for d in [BACKUP_DIR, READY_DIR, RAW_DIR]:
        candidate = d / output_name
        if candidate.exists():
            source = candidate
            break

    if not source:
        # Use raccoon poker as a test bed
        raccoon = READY_DIR / "news_cctv_raccoon_poker.mp4"
        if raccoon.exists():
            source = raccoon
            print(f"  No video for {idea_id}, using raccoon poker as test bed")
        else:
            print(f"  No video found to test overlay on")
            return

    import shutil
    test_path = RAW_DIR / f"test_overlay_{idea_id}.mp4"
    shutil.copy2(str(source), str(test_path))

    print(f"\nTesting overlay on: {source.name}")
    if meta["format"] == "cctv":
        print(f"  Applying CCTV overlay...")
        add_cctv_overlay(test_path, idea_id, meta.get("time_of_day", "night"))
    print(f"  Applying news overlay...")
    result = add_news_overlay(test_path, idea_id, meta)

    if result:
        print(f"  Overlay SUCCESS")
        subprocess.run(["open", str(test_path)])
    else:
        print(f"  Overlay FAILED")
        test_path.unlink(missing_ok=True)


def cmd_approve_video(idea_id):
    if idea_id not in VIDEO_IDEAS:
        print(f"Unknown idea: {idea_id}")
        return

    meta = VIDEO_IDEAS[idea_id]
    output_name = f"{meta['format']}_{idea_id.replace(meta['format'] + '_', '', 1)}.mp4"
    review_path = REVIEW_DIR / output_name

    if not review_path.exists():
        print(f"No video in review for {idea_id}")
        print(f"  Review dir: {REVIEW_DIR}")
        videos = list(REVIEW_DIR.glob("*.mp4"))
        if videos:
            print(f"  Available: {', '.join(v.name for v in videos)}")
        return

    ready_path = READY_DIR / output_name
    import shutil
    shutil.move(str(review_path), str(ready_path))

    ideas = _load_ideas()
    if idea_id in ideas:
        ideas[idea_id]["status"] = "approved_ready"
        ideas[idea_id]["ready_path"] = str(ready_path)
        ideas[idea_id]["approved_at"] = datetime.now(CT).isoformat()
    _save_ideas(ideas)

    ready_count = len(list(READY_DIR.glob("*.mp4")))
    print(f"  APPROVED: {output_name} moved to ready/")
    print(f"  Pipeline: {ready_count}/{PIPELINE_TARGET}")

    if ready_count >= PIPELINE_TARGET:
        _notify(f"515 pipeline FULL: {ready_count} videos ready")


def cmd_reject_video(idea_id, reason=""):
    if idea_id not in VIDEO_IDEAS:
        print(f"Unknown idea: {idea_id}")
        return

    meta = VIDEO_IDEAS[idea_id]
    output_name = f"{meta['format']}_{idea_id.replace(meta['format'] + '_', '', 1)}.mp4"
    review_path = REVIEW_DIR / output_name

    if not review_path.exists():
        print(f"No video in review for {idea_id}")
        return

    review_path.unlink()
    print(f"  REJECTED: {output_name} deleted from review/")
    if reason:
        print(f"  Reason: {reason}")
    print(f"  To re-generate: python3 515_video_gen.py produce {idea_id}")

    ideas = _load_ideas()
    if idea_id in ideas:
        ideas[idea_id]["status"] = "rejected_video"
        ideas[idea_id]["rejected_at"] = datetime.now(CT).isoformat()
        ideas[idea_id]["reject_reason"] = reason
    _save_ideas(ideas)


def cmd_review():
    videos = sorted(REVIEW_DIR.glob("*.mp4"))
    if not videos:
        print("No videos awaiting review.")
        return

    print(f"\nVIDEOS AWAITING REVIEW ({len(videos)}):")
    print("-" * 60)
    for v in videos:
        size_mb = v.stat().st_size / (1024 * 1024)
        dur = _video_info(v)

        # Run quality checks
        qc = _quality_check(v)
        fails = [c for c in qc if not c[1]]
        status = f"{len(fails)} QC FAIL" if fails else "QC PASS"

        # Try to find matching idea_id
        matched_id = None
        for vid, meta in VIDEO_IDEAS.items():
            expected = f"{meta['format']}_{vid.replace(meta['format'] + '_', '', 1)}.mp4"
            if v.name == expected:
                matched_id = vid
                break

        title = VIDEO_IDEAS[matched_id]['title'] if matched_id else v.name
        print(f"  [{status:<10}] {title:<35} {size_mb:.1f}MB  {dur}")
        if fails:
            for name, _, detail in fails:
                print(f"             {name}: {detail}")
        if matched_id:
            print(f"             approve: python3 515_video_gen.py approve-video {matched_id}")
    print()


def auto_select_format(idea):
    """Pick format based on camera angle and scene type."""
    title = (idea.get("title", "") + " " + idea.get("description", "")).lower()
    angle = idea.get("camera_angle", "").lower()
    location = idea.get("location", "").lower()

    # News: breaking/newsworthy events, celebrity, records, investigations
    news_signals = ["breaking", "news", "report", "investigation", "record",
                    "championship", "announces", "press conference", "exclusive",
                    "witness", "authorities", "confirmed", "official"]
    if any(s in title for s in news_signals):
        return "news"

    # CCTV: elevated angle, night, security camera vibe, surveillance
    cctv_signals = ["security", "cctv", "surveillance", "caught on camera",
                    "overnight", "nighttime", "night shift", "3am", "2am", "1am",
                    "4am", "midnight", "after hours", "sneaking", "heist",
                    "break in", "trespassing", "stealing"]
    elevated_angles = ["overhead", "elevated", "above", "bird", "high angle",
                       "security cam", "mounted", "ceiling", "corner"]
    if any(s in title for s in cctv_signals) or any(a in angle for a in elevated_angles):
        return "cctv"

    # iPhone: ground level, someone filming, reaction, POV
    return "iphone"


def _load_ideas_bank():
    if IDEAS_BANK_FILE.exists():
        return json.loads(IDEAS_BANK_FILE.read_text())
    return []


def _save_ideas_bank(bank):
    IDEAS_BANK_FILE.write_text(json.dumps(bank, indent=2) + "\n")


def cmd_ideas(category=None):
    bank = _load_ideas_bank()
    if not bank:
        print("No ideas bank found. Run idea generation first.")
        return

    if category:
        bank = [i for i in bank if i.get("category") == category]

    categories = {}
    for idea in bank:
        cat = idea.get("category", "uncategorized")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(idea)

    approved = sum(1 for i in bank if i.get("status") == "approved")
    declined = sum(1 for i in bank if i.get("status") == "declined")
    pending = sum(1 for i in bank if i.get("status") == "pending")

    print(f"\n515 IDEAS BANK — {len(bank)} ideas")
    print(f"  Approved: {approved} | Declined: {declined} | Pending: {pending}")
    print(f"{'='*70}")

    for cat, ideas in sorted(categories.items()):
        print(f"\n  [{cat.upper()}] ({len(ideas)} ideas)")
        print(f"  {'-'*60}")
        for idea in ideas:
            st = idea.get("status", "pending")
            icon = {"approved": "Y", "declined": "X", "pending": " ", "prompted": "P"}.get(st, "?")
            fmt = idea.get("format", "?")
            print(f"    [{icon}] [{fmt:<6}] {idea['id']:<35} {idea['title']}")

    print(f"\n  Approve:  python3 515_video_gen.py approve-idea <id> [<id2> ...]")
    print(f"  Decline:  python3 515_video_gen.py decline-idea <id> [<id2> ...]")


def cmd_approve_idea(idea_ids):
    bank = _load_ideas_bank()
    id_map = {i["id"]: i for i in bank}
    count = 0
    for iid in idea_ids:
        if iid in id_map:
            idea = id_map[iid]
            idea["status"] = "approved"
            if not idea.get("format") or idea["format"] == "?":
                idea["format"] = auto_select_format(idea)
                print(f"  Approved: {idea['title']}  [auto-format: {idea['format']}]")
            else:
                print(f"  Approved: {idea['title']}  [{idea['format']}]")
            count += 1
        else:
            print(f"  Not found: {iid}")
    _save_ideas_bank(bank)
    approved = sum(1 for i in bank if i.get("status") == "approved")
    print(f"\n  Total approved: {approved}/{len(bank)}")


def cmd_decline_idea(idea_ids):
    bank = _load_ideas_bank()
    id_map = {i["id"]: i for i in bank}
    count = 0
    for iid in idea_ids:
        if iid in id_map:
            id_map[iid]["status"] = "declined"
            count += 1
            print(f"  Declined: {id_map[iid]['title']}")
        else:
            print(f"  Not found: {iid}")
    _save_ideas_bank(bank)
    declined = sum(1 for i in bank if i.get("status") == "declined")
    print(f"\n  Total declined: {declined}/{len(bank)}")


def cmd_preview_audio(idea_id):
    if idea_id not in VIDEO_IDEAS:
        print(f"Unknown idea: {idea_id}")
        return

    meta = VIDEO_IDEAS[idea_id]
    print(f"\nAudio preview for: {meta['title']}")
    print(f"  Format: {meta['format']} | Time: {meta.get('time_of_day', '?')}")

    if idea_id in AUDIO_SPECS:
        print(f"  Source: Hand-tuned spec")
    else:
        print(f"  Source: Auto-analyzed from scene prompt")

    spec = AUDIO_SPECS.get(idea_id) or auto_audio_spec(idea_id)
    missing = check_sfx_availability(idea_id)
    print_timing_map(idea_id)

    if missing:
        print(f"\n  MISSING SFX: {', '.join(missing)}")
    print(f"\n  Scene prompt excerpt:")
    print(f"  {meta['scene_prompt'][:200]}...")


def cmd_sync_audio(idea_id):
    """Re-sync audio to an existing video using motion analysis."""
    if idea_id not in VIDEO_IDEAS:
        print(f"Unknown idea: {idea_id}")
        return

    meta = VIDEO_IDEAS[idea_id]
    output_name = f"{meta['format']}_{idea_id.replace(meta['format'] + '_', '', 1)}.mp4"
    backup_path = BACKUP_DIR / output_name

    if not backup_path.exists():
        # Try ready/ or review/
        for d in [READY_DIR, REVIEW_DIR, RAW_DIR]:
            candidate = d / output_name
            if candidate.exists():
                backup_path = candidate
                break

    if not backup_path.exists():
        print(f"No video found for {idea_id}")
        print(f"  Checked: backup/, ready/, review/, raw/")
        return

    print(f"\nRe-syncing audio for: {meta['title']}")
    print(f"  Video: {backup_path}")

    # Analyze motion on the no-audio backup (or whatever we have)
    synced_spec = sync_audio_to_video(idea_id, backup_path)
    if not synced_spec or not synced_spec.get("layers"):
        print(f"  Motion analysis found nothing — cannot sync")
        return

    AUDIO_SPECS[idea_id] = synced_spec

    # Re-apply audio from backup
    import shutil
    work_path = RAW_DIR / output_name
    actual_backup = BACKUP_DIR / output_name
    if actual_backup.exists():
        shutil.copy2(str(actual_backup), str(work_path))
    else:
        shutil.copy2(str(backup_path), str(work_path))

    print(f"\n  SYNCED AUDIO TIMING:")
    print_timing_map(idea_id)

    print(f"\n  Mixing audio...")
    result = apply_audio_mix(work_path, idea_id)
    if result:
        # Move to review
        review_path = REVIEW_DIR / output_name
        shutil.copy2(str(work_path), str(review_path))
        print(f"\n  Re-synced video in review: {review_path.name}")
        print(f"  Approve: python3 515_video_gen.py approve-video {idea_id}")
        subprocess.run(["open", str(review_path)])
    else:
        print(f"  Audio re-mix failed")


def _preflight_check(scene_prompt, time_of_day, fmt, title, headline_text):
    """Catch prompt conflicts BEFORE spending $1.68. Returns list of issues."""
    issues = []
    prompt_lower = scene_prompt.lower()
    title_lower = title.lower()
    combined = prompt_lower + " " + title_lower

    # Time vs prompt conflicts
    night_words = ["night", "dark", "moonlight", "stars", "glow", "beam of light",
                   "ufo", "alien", "ghost", "haunt", "flashlight", "headlight",
                   "midnight", "3am", "2am", "shadow creature", "creepy"]
    day_words = ["bright daytime", "sunny", "sunlight", "midday", "afternoon"]
    evening_words = ["sunset", "dusk", "golden hour", "twilight", "campfire"]

    has_night = any(w in combined for w in night_words)
    has_day = any(w in combined for w in day_words)
    has_evening = any(w in combined for w in evening_words)

    if time_of_day == "day" and has_night and not has_day:
        issues.append(f"CONFLICT: --time is 'day' but prompt/title has night content ({[w for w in night_words if w in combined][:3]})")
    if time_of_day == "night" and has_day:
        issues.append(f"CONFLICT: --time is 'night' but prompt says daytime ({[w for w in day_words if w in prompt_lower][:2]})")
    if "bright daytime" in prompt_lower and has_night:
        issues.append("CONFLICT: Prompt says 'bright daytime lighting' but also has night content")
    if "nighttime lighting" in prompt_lower and has_day:
        issues.append("CONFLICT: Prompt says 'nighttime lighting' but also has day content")

    # Prompt quality checks
    if len(scene_prompt) < 50:
        issues.append(f"WEAK PROMPT: Only {len(scene_prompt)} chars. Good prompts are 150-400 chars with specific motion verbs.")
    generic_verbs = ["moves", "goes", "does", "walks", "comes", "gets"]
    found_generic = [v for v in generic_verbs if v in prompt_lower]
    if found_generic:
        issues.append(f"GENERIC VERBS: {found_generic} — use specific verbs like 'lurches', 'slams', 'stumbles', 'darts'")

    # Headline check — ALL videos get news overlay
    if not headline_text:
        issues.append("No --headline text. The news overlay will say 'at 515 Scenic Cabins on Lake Fork' — is that what you want?")

    # Scene setup leak — prompt should describe MOTION, not setup
    setup_phrases = ["there is", "there are", "the scene shows", "we see", "the camera shows",
                     "in this scene", "the setting is", "placed on", "sitting at"]
    found_setup = [p for p in setup_phrases if p in prompt_lower]
    if found_setup:
        issues.append(f"SETUP LEAK: Prompt describes scene setup ({found_setup[:2]}) instead of motion. The starting frame already has the setup — prompt should only describe what MOVES.")

    # Contradictory motion
    if "single continuous shot" not in prompt_lower and "no cuts" not in prompt_lower:
        issues.append("MISSING: Add 'Single continuous shot, no cuts.' to prevent jump cuts.")

    # PHYSICAL REALITY — catch illogical scenarios before wasting $1.68
    aquatic = ["bass", "fish", "catfish", "crappie", "perch", "trout"]
    water_words = ["water", "lake", "dock", "boat", "swim", "splash", "flop out of",
                   "jump from", "flopping", "bucket", "caught", "fishing", "reel"]
    for animal in aquatic:
        if animal in prompt_lower:
            has_water_context = any(w in prompt_lower for w in water_words)
            if not has_water_context:
                issues.append(
                    f"AUTO-FIX: '{animal}' on dry land with no water context — "
                    f"will auto-substitute with the Rowdy Raccoons at generation time. "
                    f"To keep the {animal}, add water context (lake, dock, bucket, fishing)."
                )

    # Check for objects appearing from nothing
    appear_words = ["suddenly appears", "materializes", "pops up", "shows up out of nowhere",
                    "just there", "appears on", "is sitting on"]
    for phrase in appear_words:
        if phrase in prompt_lower:
            issues.append(
                f"REALITY: '{phrase}' — objects can't appear from nothing. "
                f"Describe WHERE it comes from (walks in from off-screen, drops from above, "
                f"was already in the starting frame, emerges from behind something)."
            )

    # Check for missing entrance descriptions for characters
    char_words = ["man", "woman", "person", "fisherman", "guest", "guy", "kid", "child"]
    action_intros = ["walks in", "enters", "approaches", "comes from", "standing", "sits",
                     "already there", "already in", "walks into frame", "from off-screen",
                     "from the left", "from the right", "from behind"]
    for char in char_words:
        if char in prompt_lower:
            has_intro = any(intro in prompt_lower for intro in action_intros)
            if not has_intro and "starting frame" not in prompt_lower:
                issues.append(
                    f"CONTEXT: '{char}' mentioned but no entrance/position described. "
                    f"Is this person already in the starting frame? Walking in from off-screen? "
                    f"Kling needs to know WHERE characters start."
                )

    return issues


def cmd_produce_dynamic(cli_args):
    """Produce a video from dashboard-generated parameters (no VIDEO_IDEAS entry needed)."""

    def _parse_dynamic_args(a):
        result = {}
        i = 0
        while i < len(a):
            if a[i].startswith("--") and i + 1 < len(a):
                key = a[i][2:]
                result[key] = a[i + 1]
                i += 2
            else:
                i += 1
        return result

    opts = _parse_dynamic_args(cli_args)
    dry_run = "--dry-run" in cli_args
    # --yes kept for backwards compat but auto-proceed is now default

    required = ["id", "composite", "format", "title", "prompt"]
    missing = [k for k in required if k not in opts]
    if missing:
        print(f"Missing required args: {', '.join('--' + m for m in missing)}")
        print(f"Usage: produce-dynamic --id ID --composite PATH --format FMT --title TITLE --prompt PROMPT [--headline TEXT] [--time day|evening|night] [--dry-run] [--yes]")
        return

    idea_id = opts["id"]
    composite_path = Path(opts["composite"]).expanduser()
    fmt = opts["format"]
    title = opts["title"]
    scene_prompt = opts["prompt"]
    headline_raw = opts.get("headline", "")
    time_of_day = opts.get("time", "day")

    # Split headline into two lines: use | delimiter, or auto-split at midpoint
    if "|" in headline_raw:
        parts = headline_raw.split("|", 1)
        headline_line1 = parts[0].strip()
        headline_line2 = parts[1].strip()
    elif len(headline_raw) > 40:
        words = headline_raw.split()
        mid = len(words) // 2
        headline_line1 = " ".join(words[:mid])
        headline_line2 = " ".join(words[mid:])
    else:
        headline_line1 = headline_raw
        headline_line2 = "at 515 Scenic Cabins on Lake Fork"

    # P14: Clean headline — strip em dashes, explanations, editorializing
    headline_raw_clean = _clean_headline(headline_raw)
    if "|" in headline_raw_clean:
        parts = headline_raw_clean.split("|", 1)
        headline_line1 = parts[0].strip()
        headline_line2 = parts[1].strip()
    elif len(headline_raw_clean) > 40:
        words = headline_raw_clean.split()
        mid = len(words) // 2
        headline_line1 = " ".join(words[:mid])
        headline_line2 = " ".join(words[mid:])
    else:
        headline_line1 = headline_raw_clean
        headline_line2 = "at 515 Scenic Cabins on Lake Fork"
    # Auto-fix character names in headline (P11)
    headline_line1 = _fix_headline_character_names(headline_line1)
    headline_line2 = _fix_headline_character_names(headline_line2)

    if not composite_path.exists():
        print(f"ABORT: Composite not found: {composite_path}")
        print(f"  Download the composite from the dashboard and save it before running this command.")
        return

    if not _get_fal_key():
        print("No key. Run: echo 'KEY' > ~/.boss_secrets/fal_key")
        return

    # === PRE-FLIGHT: catch conflicts before spending $1.68 ===
    issues = _preflight_check(scene_prompt, time_of_day, fmt, title, headline_raw)

    print(f"\n{'='*60}")
    print(f"PRE-FLIGHT CHECK: {title}")
    print(f"{'='*60}")
    print(f"  ID:        {idea_id}")
    print(f"  Format:    {fmt}")
    print(f"  Time:      {time_of_day}")
    print(f"  Composite: {composite_path.name}")
    print(f"  Headline:  {headline_line1}")
    print(f"             {headline_line2}")
    print(f"  Prompt:    {scene_prompt[:200]}{'...' if len(scene_prompt)>200 else ''}")
    print(f"  Cost:      ~$1.68")

    if issues:
        print(f"\n  {'!'*50}")
        print(f"  ISSUES NOTED ({len(issues)}):")
        print(f"  {'!'*50}")
        for issue in issues:
            print(f"  - {issue}")
        print(f"\n  Auto-proceeding — issues are informational only.")
    else:
        print(f"\n  All pre-flight checks passed.")

    if dry_run:
        if issues:
            print(PROMPT_TEMPLATE_GUIDE)
        print("  DRY RUN — remove --dry-run to generate.")
        return

    # === PASSED — proceed with generation ===
    dest = COMPOSITES_DIR / f"{idea_id}_start.png"
    import shutil
    if Path(composite_path).resolve() != dest.resolve():
        shutil.copy2(str(composite_path), str(dest))
        print(f"\n  Composite copied to: {dest}")
    else:
        print(f"\n  Composite already in place: {dest}")

    meta = {
        "format": fmt,
        "title": title,
        "plate": f"composites/{idea_id}_start.png",
        "scene_prompt": scene_prompt,
        "time_of_day": time_of_day,
        "headline": (headline_line1, headline_line2),
        "clear_instructions": "",
    }
    VIDEO_IDEAS[idea_id] = meta

    plate_base = Path(meta["plate"]).stem
    if not check_plate_available(plate_base):
        last = plate_last_used(plate_base)
        print(f"BLOCKED: Plate '{plate_base}' was used on {last}")
        print(f"  Each plate can only be used once per {PLATE_COOLDOWN_DAYS} days")
        return

    spec = AUDIO_SPECS.get(idea_id) or auto_audio_spec(idea_id)
    missing_sfx = check_sfx_availability(idea_id)
    print(f"\n{'='*60}")
    print(f"GENERATING: {title}")
    print(f"{'='*60}")
    print(f"  Format: {fmt} | Time: {time_of_day} | Composite: {composite_path.name}")
    if missing_sfx:
        print(f"  WARNING: Missing SFX: {', '.join(missing_sfx)}")

    result = generate_video(idea_id)
    if result:
        _record_plate_use(plate_base)
        ready_path = REVIEW_DIR / result.name
        print(f"\n  IN REVIEW: {ready_path}")
        print(f"  Backup: {BACKUP_DIR / result.name}")
        print(f"\n  Audio was synced to actual video motion.")
        print(f"  To approve:    python3 515_video_gen.py approve-video {idea_id}")
        print(f"  To reject:     python3 515_video_gen.py reject-video {idea_id}")
        subprocess.run(["open", str(ready_path)])


# ──────────────────────────────────────────────────────────────
# LOCAL API SERVER — dashboard calls this to generate videos
# Start: python3 515_video_gen.py serve
# Dashboard hits http://localhost:5155/api/generate via POST
# ──────────────────────────────────────────────────────────────

_SERVE_PORT = 5155
_current_job = {"status": "idle", "progress": "", "result": None, "id": None}


def cmd_serve():
    """Start local HTTP API for dashboard integration."""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import threading

    class Handler(BaseHTTPRequestHandler):
        def _cors(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def do_OPTIONS(self):
            self.send_response(200)
            self._cors()
            self.end_headers()

        def do_GET(self):
            if self.path == "/api/health":
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True}).encode())

            elif self.path == "/api/status":
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(_current_job).encode())

            else:
                self.send_response(404)
                self._cors()
                self.end_headers()

        def do_POST(self):
            if self.path == "/api/generate":
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length)) if length else {}

                if _current_job["status"] == "running":
                    self.send_response(409)
                    self._cors()
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "error": "Generation already in progress",
                        "id": _current_job["id"],
                    }).encode())
                    return

                required = ["id", "format", "title", "prompt", "composite_b64"]
                missing = [k for k in required if k not in body]
                if missing:
                    self.send_response(400)
                    self._cors()
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": f"Missing: {missing}"}).encode())
                    return

                # Save composite from base64
                import base64
                comp_data = base64.b64decode(body["composite_b64"])
                comp_path = COMPOSITES_DIR / f"{body['id']}_start.png"
                comp_path.write_bytes(comp_data)

                # Start generation in background thread
                def _run_generation():
                    try:
                        _current_job["status"] = "running"
                        _current_job["id"] = body["id"]
                        _current_job["progress"] = "Starting..."
                        _current_job["result"] = None

                        idea_id = body["id"]
                        fmt = body["format"]
                        title = body["title"]
                        scene_prompt = body["prompt"]
                        headline_raw = body.get("headline", "")
                        time_of_day = body.get("time", "day")

                        # P14: Clean headline + split
                        headline_clean = _clean_headline(headline_raw)
                        if "|" in headline_clean:
                            parts = headline_clean.split("|", 1)
                            hl1, hl2 = parts[0].strip(), parts[1].strip()
                        elif len(headline_clean) > 40:
                            words = headline_clean.split()
                            mid = len(words) // 2
                            hl1 = " ".join(words[:mid])
                            hl2 = " ".join(words[mid:])
                        else:
                            hl1 = headline_clean
                            hl2 = "at 515 Scenic Cabins on Lake Fork"

                        hl1 = _fix_headline_character_names(hl1)
                        hl2 = _fix_headline_character_names(hl2)

                        meta = {
                            "format": fmt,
                            "title": title,
                            "plate": f"composites/{idea_id}_start.png",
                            "scene_prompt": scene_prompt,
                            "time_of_day": time_of_day,
                            "headline": (hl1, hl2),
                            "clear_instructions": "",
                        }
                        VIDEO_IDEAS[idea_id] = meta

                        plate_base = Path(meta["plate"]).stem

                        # Clear cooldown for re-generations
                        usage = _load_plate_usage()
                        usage.pop(plate_base, None)
                        _save_plate_usage(usage)

                        _current_job["progress"] = "Uploading to fal.ai..."
                        result = generate_video(idea_id)

                        if result:
                            _record_plate_use(plate_base)
                            review_path = REVIEW_DIR / result.name
                            _current_job["status"] = "done"
                            _current_job["progress"] = "Complete"
                            _current_job["result"] = {
                                "video_path": str(review_path),
                                "video_name": result.name,
                                "success": True,
                            }
                            subprocess.run(["open", str(review_path)])
                        else:
                            _current_job["status"] = "error"
                            _current_job["progress"] = "Generation failed"
                            _current_job["result"] = {"success": False, "error": "generate_video returned None"}
                    except Exception as e:
                        _current_job["status"] = "error"
                        _current_job["progress"] = f"Error: {str(e)}"
                        _current_job["result"] = {"success": False, "error": str(e)}

                t = threading.Thread(target=_run_generation, daemon=True)
                t.start()

                self.send_response(202)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "accepted": True,
                    "id": body["id"],
                    "cost": "$1.68",
                }).encode())

            elif self.path == "/api/post-to-buffer":
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length)) if length else {}

                tk_caption = body.get("tiktok_caption", "")
                ig_caption = body.get("instagram_caption", "")
                if not tk_caption and not ig_caption:
                    self.send_response(400)
                    self._cors()
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "No captions provided"}).encode())
                    return

                from pathlib import Path as _P
                token = _P.home().joinpath(".boss_secrets/buffer_515_token").read_text().strip() if _P.home().joinpath(".boss_secrets/buffer_515_token").exists() else ""
                if not token:
                    self.send_response(500)
                    self._cors()
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "No Buffer token"}).encode())
                    return

                BUFFER_GQL = "https://api.buffer.com/graphql"
                TK_CHANNEL = "6a566dc680cc80cdcab2ee69"
                IG_CHANNEL = "6a566b6c80cc80cdcab2bb74"

                def _buffer_gql(query):
                    body_bytes = json.dumps({"query": query}).encode()
                    req = urllib.request.Request(BUFFER_GQL, data=body_bytes, method="POST")
                    req.add_header("Authorization", f"Bearer {token}")
                    req.add_header("Content-Type", "application/json")
                    resp = urllib.request.urlopen(req, timeout=15)
                    return json.loads(resp.read())

                def _post(text, channel_id, service):
                    escaped = (text.replace('\\', '\\\\').replace('"', '\\"')
                               .replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t'))
                    meta = ', metadata: { instagram: { type: post, shouldShareToFeed: true } }' if service == "instagram" else ""
                    mutation = (
                        'mutation { createPost(input: { text: "' + escaped + '"'
                        + ', channelId: "' + channel_id + '"'
                        + meta
                        + ', schedulingType: automatic, mode: addToQueue'
                        + ' }) { ... on PostActionSuccess { post { id text dueAt } }'
                        + ' ... on MutationError { message } } }'
                    )
                    return _buffer_gql(mutation)

                results = {}
                errors = []
                if tk_caption:
                    try:
                        r = _post(tk_caption, TK_CHANNEL, "tiktok")
                        post_data = r.get("data", {}).get("createPost", {})
                        if "post" in post_data:
                            results["tiktok"] = {"ok": True, "due": post_data["post"].get("dueAt", "")}
                        else:
                            errors.append(f"TikTok: {post_data.get('message', str(r))}")
                    except Exception as e:
                        errors.append(f"TikTok: {e}")

                if ig_caption:
                    try:
                        r = _post(ig_caption, IG_CHANNEL, "instagram")
                        post_data = r.get("data", {}).get("createPost", {})
                        if "post" in post_data:
                            results["instagram"] = {"ok": True, "due": post_data["post"].get("dueAt", "")}
                        else:
                            errors.append(f"Instagram: {post_data.get('message', str(r))}")
                    except Exception as e:
                        errors.append(f"Instagram: {e}")

                self.send_response(200 if not errors else 207)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "results": results,
                    "errors": errors,
                    "id": body.get("id", ""),
                }).encode())

            else:
                self.send_response(404)
                self._cors()
                self.end_headers()

        def log_message(self, format, *args):
            print(f"  [API] {args[0]}")

    # Patch generate_video to update progress
    original_print = print
    def _progress_print(*args, **kwargs):
        msg = " ".join(str(a) for a in args)
        if _current_job["status"] == "running":
            # Extract key progress messages
            for marker in ["Uploading", "Generating", "IN_PROGRESS", "Completed",
                           "Downloading", "Applying", "Adding", "Mixing", "QUALITY"]:
                if marker in msg:
                    _current_job["progress"] = msg.strip()[:200]
                    break
        original_print(*args, **kwargs)

    import builtins
    builtins.print = _progress_print

    server = HTTPServer(("127.0.0.1", _SERVE_PORT), Handler)
    print(f"515 Video API running on http://localhost:{_SERVE_PORT}")
    print(f"  Dashboard can now generate videos directly.")
    print(f"  Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        builtins.print = original_print


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    cmd = args[0]
    if cmd == "pipeline":
        cmd_pipeline()
    elif cmd == "batch":
        cmd_batch()
    elif cmd == "clean":
        cmd_clean()
    elif cmd == "test-overlay" and len(args) > 1:
        cmd_test_overlay(args[1])
    elif cmd == "status":
        cmd_status()
    elif cmd == "generate":
        sid = None
        if "--id" in args:
            idx = args.index("--id")
            if idx + 1 < len(args):
                sid = args[idx + 1]
        cmd_generate(all_mode="--all" in args, specific_id=sid)
    elif cmd == "produce" and len(args) > 1:
        cmd_produce(args[1])
    elif cmd == "produce-dynamic":
        cmd_produce_dynamic(args[1:])
    elif cmd == "retime" and len(args) > 1:
        cmd_retime(args[1], args[2:])
    elif cmd == "sfx":
        cmd_sfx()
    elif cmd == "preview" and len(args) > 1:
        cmd_preview_audio(args[1])
    elif cmd == "sync-audio" and len(args) > 1:
        cmd_sync_audio(args[1])
    elif cmd == "daily":
        cmd_daily()
    elif cmd == "list":
        cmd_list()
    elif cmd == "check" and len(args) > 1:
        cmd_check(args[1])
    elif cmd == "approve" and len(args) > 1:
        cmd_approve(args[1])
    elif cmd == "plates":
        cmd_plates()
    elif cmd == "approve-video" and len(args) > 1:
        cmd_approve_video(args[1])
    elif cmd == "reject-video" and len(args) > 1:
        reason = " ".join(args[2:]) if len(args) > 2 else ""
        cmd_reject_video(args[1], reason)
    elif cmd == "review":
        cmd_review()
    elif cmd == "ideas":
        cat = args[1] if len(args) > 1 else None
        cmd_ideas(cat)
    elif cmd == "approve-idea" and len(args) > 1:
        cmd_approve_idea(args[1:])
    elif cmd == "decline-idea" and len(args) > 1:
        cmd_decline_idea(args[1:])
    elif cmd == "grok-prompt" and len(args) > 1:
        cmd_grok_prompt(args[1])
    elif cmd == "compose-signs":
        _compose_sign_on_plate()
    elif cmd == "serve":
        cmd_serve()
    else:
        print(__doc__)
