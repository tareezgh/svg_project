GEMINI_API_KEY = "AIzaSyAc3N0F9nGQ4pDoGeiQGBOZDZofQVTzHbA"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
# DEFAULT_PROMPT = "Give a rich description of what is highlighted assuming it was input for a text to image model only. be to the point for the task."
DEMO_MODE = False
# DEFAULT_PROMPT = (
#     "For each PNG segment I send, please provide a **separate description**. "
#     "Give a rich, concise description assuming it was input for a text-to-image model. "
#     "Respond with a JSON array of objects like: "
#     "[{'id': '<file_name>', 'description': '<description>'}, ...]. "
#     "Use the exact file names from the list below. "
# )


# DEFAULT_PROMPT = "Describe *only* the object or area highlighted with a red stroke in this image. Focus on its appearance and what it represents. Be concise and to the point, suitable for a text-to-image model input."

# DEFAULT_PROMPT = "Provide a **rich, detailed description** of *only* the object or area highlighted in red in this image. Describe it as if you were writing a prompt for a text-to-image model. Focus on its **appearance, shape, colors, textures, patterns, and artistic style**. Use clear, descriptive language that a text-to-image model would understand and render accurately. Avoid repeating the file name or any unnecessary information. Be thorough but to the point for the task."

# DEFAULT_PROMPT = (
#     "Provide a rich, detailed description of *only* the object or area highlighted in red in this image. "
#     "Describe it as if you were writing a prompt for a text-to-image model. "
#     "Focus on its appearance, shape, colors, textures, patterns, and artistic style. "
#     "If the highlighted area represents a specific part of an object (e.g., tail, leaf, headlight), "
#     "be sure to specify that part and describe its relationship to the object as a whole. "
#     "Use the following Markdown format:\n\n"
#     "**filename.png**\n"
#     "* description\n\n"
#     "Only include the filename and its corresponding description. "
#     "Do not include any additional text."
# )

# DEFAULT_PROMPT = (
#     "Provide a rich, detailed description of *only* the object or area highlighted in red in this image. "
#     "Describe it as if you were writing a prompt for a text-to-image model. "
#     "Focus on its appearance, shape, colors, textures, patterns, and artistic style. "
#     "If the highlighted area represents a specific part of an object (e.g., tail, leaf, headlight), "
#     "be sure to specify that part and describe its relationship to the object as a whole. "
#     "Do not mention the highlighting itself or the red stroke—only describe the object or area as it would appear naturally. "
#     "Use the following Markdown format:\n\n"
#     "**filename.png**\n"
#     "* description\n\n"
#     "Only include the filename and its corresponding description. "
#     "Do not include any additional text."
# )

# DEFAULT_PROMPT = (
#     "Describe *only* the object or area outlined with a red stroke in this image. "
#     "This red stroke is *only a visual marker* and does not belong to the actual object. "
#     "Do not describe the red stroke, red borders, or any red color unless it is clearly part of the object’s appearance itself. "
#     "Focus only on the object’s natural appearance without the red highlight. "
#     "Give a clear, concise, and visually rich description suitable as input for a text-to-image model. "
#     "If the object is part of something larger (e.g., part of a person, screen, icon), specify what it is. "
#     "Use the following Markdown format:\n\n"
#     "**filename.png**\n"
#     "* description\n\n"
#     "Only include one description per filename. Do not include any introductory text or explanations."
# )


DEFAULT_PROMPT1 = (
    "You are given a series of images, each with a specific object or region outlined in red. "
    "Your task is to describe only the object or region inside the red outline, using the visual context of the entire scene to understand what it represents. "
    "The red outline is only a marker — do not mention or describe the red stroke, border, or any red color unless it clearly belongs to the object itself. "
    "Focus on what the highlighted area is, how it looks, and what it represents. If it's part of a larger object (like a table leg, candle, or graph arrow), identify it precisely. "
    "Do not default to vague terms like 'red dot' or 'red something' — use clues from the full scene to determine what the object is. "
    "Write a rich, vivid description suitable for a text-to-image generation model. Use descriptive language for the object’s shape, material, size, position, and purpose. "
    "Return the result in the following Markdown format:\n\n"
    "**filename.png**\n"
    "* description\n\n"
    "Only include one description per image. Do not add any extra commentary, prefaces, or summaries."
)

DEFAULT_PROMPT2 = (
    "You are given a set of images, each containing a single object or region highlighted with a red outline. "
    "Your task is to generate a **rich, detailed description** of the object or region inside the red outline. "
    "This description should be suitable for input to a **text-to-image generation model**, so be specific and vivid. "
    "Use the visual context of the full image to identify what the highlighted area is — its type, function, and appearance. "
    "Do **not** mention the red outline or red color unless it is a natural part of the object itself. "
    "Avoid generic descriptions like 'red thing' or 'highlighted part'. Instead, describe what the object is, its material, shape, color, texture, and role in the scene (e.g., 'a candle on a cake', 'a down arrow on a financial chart', 'a laptop screen showing a login form'). "
    "Focus on what the object represents in the real world, and what its presence suggests about the scene. "
    "If it is part of a larger object (e.g., a leg of a chair, the screen of a laptop), make that relationship clear. "
    "Respond using **only** the following Markdown format:\n\n"
    "**filename.png**\n"
    "* A rich, concise, descriptive sentence of the highlighted object\n\n"
    "Return one entry per image. Do not include any introductions, summaries, or extra commentary."
    "The order of images and filenames MUST be preserved."
    "Return descriptions for each image immediately following its filename."
    "DO NOT reorder or group images differently."
)


DEFAULT_PROMPT11 = (
    "You are given a set of images. In each image, the background is darkened or obscured, "
    "and **only one object or region is clearly visible and unobstructed**. "
    "Your task is to generate a rich, specific, and detailed description of **only the visible part** of the image. "
    "Do not describe the scene. Do not infer based on layout, screen, or recurring patterns. "
    "Only describe the visible shape or object — its color, shape, material, and what it appears to be. "
    "Avoid guessing or repeating descriptions unless they are clearly identical visually.\n\n"

    "Return your answer in the following format, exactly:\n\n"
    "**filename.png**\n"
    "* A vivid, concise description of the visible object\n\n"

    "Return one entry per image. Do not summarize, group, or comment. No extra text. Just one markdown entry per image."
)

DEFAULT_PROMPT20 = (
    "You are given a set of images. In each image, most of the scene is darkened, "
    "and **one specific object or region remains fully visible and unobstructed**. "
    "This clearly visible region is your target.\n\n"

    "Your task is to generate a **rich, specific, and context-aware description of the visible region only**. "
    "Use the rest of the scene **only to understand what the visible part is** — for example, whether it's part of a desk, floor, plant, screen, person, etc."
    "This description should be suitable for input to a **text-to-image generation model**.\n\n"

    "✅ Describe what the object is (e.g. 'an orange desk surface' or 'a green plant pot')\n"
    "✅ Mention material, shape, color, and its purpose or role **if known from the scene**\n"
    "❌ Do NOT describe the full scene\n"
    "❌ Do NOT mention darkened areas\n"
    "❌ Do NOT guess based on repeating patterns from other images\n"
    "❌ Do NOT use abstract shapes like 'trapezoid' unless the object truly has no identity\n\n"

    "Respond in this exact Markdown format:\n\n"
    "**filename.png**\n"
    "* A specific, clear description of the visible object or region\n\n"

    "Return one entry per image. No commentary, no summaries, no extra formatting."
)

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
