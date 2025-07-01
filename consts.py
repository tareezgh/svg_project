GEMINI_API_KEY = "AIzaSyAc3N0F9nGQ4pDoGeiQGBOZDZofQVTzHbA"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

DEFAULT_PROMPT = (
 
    "You are given an image, most of the scene is darkened, "
    "and **one specific object or region remains fully visible and unobstructed**. "
    "This clearly visible region is your target.\n\n"

    "Your task is to generate a **rich, specific, and context-aware description of the visible region only**. "
    "Use the rest of the scene **only to understand what the visible part is** — for example, whether it's part of a desk, floor, plant, screen, person, etc.\n\n"

    "✅ Describe what the object is (e.g. 'an orange desk surface' or 'a green plant pot')\n"
    "✅ Mention material, shape, color, and its purpose or role **if known from the scene**\n"
    "❌ Do NOT describe the full scene\n"
    "❌ Do NOT mention darkened areas\n"
    "❌ Do NOT guess based on repeating patterns from other images\n"
    "❌ Do NOT use abstract shapes like 'trapezoid' unless the object truly has no identity\n\n"

    "After each image you will see its filename written like this:\n"
    "**filename.png**\n\n"
    "Immediately below the filename, write:\n"
    "* your description\n\n"

    "Only return your output in this exact format for each image:\n"
    "**filename.png**\n"
    "* A clear and specific description\n\n"

    "No commentary, no extra text. Just filename and description."
)
