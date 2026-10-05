from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class VisualStyle:
    name: str
    label: str
    description: str
    frame_prefix: str
    house_look: str
    video_motion_prompt: str
    character_style_guidance: str
    allow_real_media: bool = False
    film_look: bool = True


VISUAL_STYLES: Mapping[str, VisualStyle] = {
    "realistic": VisualStyle(
        name="realistic",
        label="Cinematic Realistic / 35mm Film",
        description="Dark cinematic documentary reenactment, 35mm anamorphic lens, low-key lighting and authentic textures.",
        frame_prefix=(
            "Vertical 9:16 photorealistic cinematic film still: the opening frame of a documentary shot. "
            "One single full-frame image - never a collage, grid, split screen or comic panels. "
            "No text, no captions, no watermark."
        ),
        house_look=(
            "Dark cinematic documentary reenactment, shot on 35mm anamorphic lens: low-key motivated lighting "
            "(candle, oil lamp, window light, dawn or dusk), deep shadows, a restrained desaturated teal-and-amber "
            "grade, fine film grain, shallow depth of field, natural imperfections. Moody and authentic, like a "
            "high-end history documentary. Never bright, glossy, oversaturated stock photography."
        ),
        video_motion_prompt=(
            "photorealistic cinematic shot with natural, realistic motion from the very first frame and a slow, "
            "steady, filmic camera move. Faces and hands stay stable and undistorted, nothing morphs or melts. "
            "Keep every person looking exactly as in the frame and keep the dark, moody lighting."
        ),
        character_style_guidance=(
            "Characters look like real, ordinary, weathered people of the period: individual faces, lived-in skin, "
            "worn clothes. Never glamorous, never model-like, never perfectly clean."
        ),
        allow_real_media=True,
        film_look=True,
    ),
    "animated": VisualStyle(
        name="animated",
        label="Stylized 2D Animation",
        description="Vibrant stylized 2D animation with expressive line art, bold color palettes, and cel-shading.",
        frame_prefix=(
            "Vertical 9:16 stylized 2D animation feature still: the opening frame of a premium animated sequence. "
            "One single full-frame image - never a collage, grid, split screen or comic panels. "
            "No text, no captions, no watermark."
        ),
        house_look=(
            "Dynamic stylized 2D animation aesthetic: crisp expressive line art, bold rich color palette, "
            "beautiful cel-shading, vibrant atmospheric lighting, painterly hand-crafted background scenery with depth, "
            "clear character silhouettes. Polished, cinematic, and modern animated film look. "
            "Never cheap flat clip-art, never 3D CGI."
        ),
        video_motion_prompt=(
            "stylized 2D animated shot with fluid expressive character movement, dynamic animated camera motion, "
            "and vivid lighting. Keep the stylized 2D animation look consistent from the first frame without morphing into 3D or photorealism."
        ),
        character_style_guidance=(
            "Characters have expressive stylized 2D animation designs: clean distinctive silhouettes, expressive facial features, "
            "bold recognizable attire. Stylized for animation while historically accurate to Nepal."
        ),
        allow_real_media=False,
        film_look=False,
    ),
    "disney": VisualStyle(
        name="disney",
        label="Disney & Pixar 3D Animation",
        description="High-budget 3D animated feature film aesthetic with rich subsurface scattering and emotive characters.",
        frame_prefix=(
            "Vertical 9:16 Disney and Pixar 3D animated feature film still: the opening frame of a high-budget 3D animated cinema scene. "
            "One single full-frame image - never a collage, grid, split screen or comic panels. "
            "No text, no captions, no watermark."
        ),
        house_look=(
            "Disney and Pixar 3D animated movie aesthetic: soft subsurface scattering on stylized skin, expressive character designs "
            "with large emotional eyes, appealing rounded silhouettes, rich warm volumetric lighting, soft cinematic depth of field, "
            "tactile cloth and hair shaders, warm saturated magical color palette. High-budget 3D animated feature film look. "
            "Never uncanny valley photorealism, never 2D."
        ),
        video_motion_prompt=(
            "3D animated feature film shot with expressive, smooth, bouncy Disney-Pixar character animation, "
            "subtle facial micro-expressions, fluid cloth movement, and cinematic 3D camera drift. "
            "Maintain the 3D animated feature look throughout."
        ),
        character_style_guidance=(
            "Characters have appealing Disney/Pixar 3D animated designs: stylized proportions, expressive emotional eyes, "
            "warm facial features, detailed charming period attire. Stylized for 3D animation while historically accurate to Nepal."
        ),
        allow_real_media=False,
        film_look=False,
    ),
    "anime": VisualStyle(
        name="anime",
        label="Anime / Ghibli Aesthetic",
        description="Nostalgic Japanese anime aesthetic inspired by Studio Ghibli and Makoto Shinkai, with painted skies and lush atmosphere.",
        frame_prefix=(
            "Vertical 9:16 Studio Ghibli and Makoto Shinkai inspired anime feature film still: the opening frame of a cinematic anime scene. "
            "One single full-frame image - never a collage, grid, split screen or comic panels. "
            "No text, no captions, no watermark."
        ),
        house_look=(
            "High-end Japanese 2D anime aesthetic inspired by Studio Ghibli and CoMix Wave: luminous painted skies and clouds, "
            "soft golden hour rim lighting, painterly hand-crafted background environments, clean expressive cel-shaded character designs, "
            "emotional atmospheric depth. Rich artistic beauty, evocative nostalgic tone."
        ),
        video_motion_prompt=(
            "cinematic 2D anime shot with fluid anime motion timing, drifting atmospheric particles, gentle wind blowing through "
            "hair and fabrics, and slow cinematic anime camera panning. Preserve the hand-drawn anime aesthetic."
        ),
        character_style_guidance=(
            "Characters have beautiful 2D anime designs: expressive anime eyes, distinctive stylized hair and period headwear, "
            "clean cel-shaded facial features, historically accurate Nepali attire adapted to high-end anime."
        ),
        allow_real_media=False,
        film_look=False,
    ),
    "dark_fantasy": VisualStyle(
        name="dark_fantasy",
        label="Dark Fantasy / Gothic Mythos",
        description="Atmospheric dark fantasy with chiaroscuro lighting, volumetric fog, embers, and grim ancient lore.",
        frame_prefix=(
            "Vertical 9:16 dark fantasy cinematic film still: the opening frame of a gothic historical dark fantasy scene. "
            "One single full-frame image - never a collage, grid, split screen or comic panels. "
            "No text, no captions, no watermark."
        ),
        house_look=(
            "Grim dark fantasy aesthetic: heavy chiaroscuro lighting, deep impenetrable shadows, volumetric fog, ash, dust "
            "and embers in the air, muted desaturated gothic color palette with piercing warm torchlight, gritty weathered "
            "armor and ragged robes, ominous ancient atmosphere. Visceral, haunting and epic."
        ),
        video_motion_prompt=(
            "dark fantasy cinematic shot with slow, menacing camera creep, drifting smoke and embers, and subtle realistic movements. "
            "Maintain the oppressive shadows and gothic atmosphere throughout without melting or distortion."
        ),
        character_style_guidance=(
            "Characters look battle-worn, grim and imposing: weathered rugged faces, dark intense gazes, shadowed features, "
            "historical Nepali period clothing showing wear, battle scars, or austere dignity."
        ),
        allow_real_media=False,
        film_look=True,
    ),
    "oil_painting": VisualStyle(
        name="oil_painting",
        label="Classical Mythic Oil Painting",
        description="Masterpiece oil painting with rich visible impasto brushstrokes, Rembrandt-style tenebrism, and canvas grain.",
        frame_prefix=(
            "Vertical 9:16 classical fine art oil painting masterpiece: the opening frame of an epic historical tableau. "
            "One single full-frame image - never a collage, grid, split screen or comic panels. "
            "No text, no captions, no watermark."
        ),
        house_look=(
            "Masterpiece classical fine-art oil painting: rich visible impasto brushstrokes, dramatic Rembrandt-style tenebrism, "
            "glowing candle and lantern light reflecting off gold and brocade fabrics, textured linen canvas grain, "
            "deep rich umber and crimson tones, museum heritage quality. Regal, timeless and majestic."
        ),
        video_motion_prompt=(
            "living oil painting shot where the classical painting subtly comes to life with slow, majestic camera push "
            "and gentle atmospheric movement of smoke, flames, and royal fabrics, preserving the painted brushstroke texture."
        ),
        character_style_guidance=(
            "Characters resemble figures in classical royal historical oil portraits: dignified postures, solemn expressive gazes, "
            "rich period attire with velvet, brocade, and ornate traditional Nepali jewelry."
        ),
        allow_real_media=False,
        film_look=True,
    ),
    "graphic_novel": VisualStyle(
        name="graphic_novel",
        label="Graphic Novel / Comic Noir",
        description="High-contrast graphic novel aesthetic with bold ink line art, heavy shadows, and halftone textures.",
        frame_prefix=(
            "Vertical 9:16 graphic novel cinematic illustration: the opening frame of a bold visual novel scene. "
            "One single full-frame image - never a collage, grid, split screen or comic panels. "
            "No text, no captions, no watermark."
        ),
        house_look=(
            "High-contrast graphic novel and comic noir aesthetic: stark black ink line art, heavy dynamic shadows, "
            "halftone dot textures, high-contrast chiaroscuro lighting, sharp angular compositions, dramatic spotlighting "
            "with vivid punchy accent colors against dark ink washes. Bold, edgy and arresting."
        ),
        video_motion_prompt=(
            "dynamic graphic novel cinematic shot with dramatic camera push-in, subtle animated ink movement, "
            "and bold comic lighting. Maintain the striking high-contrast ink and halftone style."
        ),
        character_style_guidance=(
            "Characters have bold graphic novel designs: sharp angular facial structures, strong jawlines, "
            "high-contrast inked features, dynamic expressive expressions, stylized period garments."
        ),
        allow_real_media=False,
        film_look=False,
    ),
    "claymation": VisualStyle(
        name="claymation",
        label="Handcrafted Claymation",
        description="Tactile handcrafted stop-motion clay animation with plasticine clay figures and miniature physical lighting.",
        frame_prefix=(
            "Vertical 9:16 tactile handcrafted stop-motion claymation still: the opening frame of a clay animated scene. "
            "One single full-frame image - never a collage, grid, split screen or comic panels. "
            "No text, no captions, no watermark."
        ),
        house_look=(
            "Handcrafted physical stop-motion claymation: tactile sculpted plasticine figures with subtle handmade fingerprint textures, "
            "miniature practical physical set lighting, shallow macro lens depth of field, charming handmade details, "
            "warm directional studio miniature spotlights. Tactile, organic and artisanal stop-motion look."
        ),
        video_motion_prompt=(
            "handcrafted stop-motion claymation shot with authentic stop-motion frame-by-frame character movement, "
            "subtle clay shifts, and miniature studio lighting. Maintain the tactile plasticine clay look."
        ),
        character_style_guidance=(
            "Characters are designed as sculpted plasticine clay figures: charming simplified facial features, "
            "sculpted clay hair and garments, tactile handcrafted proportions, historically accurate Nepali styling."
        ),
        allow_real_media=False,
        film_look=False,
    ),
    "vintage_documentary": VisualStyle(
        name="vintage_documentary",
        label="Vintage Archival Documentary",
        description="Authentic vintage 16mm/35mm analog film aesthetic with Kodachrome/sepia tones, subtle gate weave, and organic grain.",
        frame_prefix=(
            "Vertical 9:16 vintage 1930s-1950s archival documentary film still: the opening frame of a restored historical reel. "
            "One single full-frame image - never a collage, grid, split screen or comic panels. "
            "No text, no captions, no watermark."
        ),
        house_look=(
            "Authentic vintage archival documentary: authentic 16mm/35mm analog film stock, rich Kodachrome and sepia tone grading, "
            "subtle film gate weave, natural emulsion scratches and warm organic film grain, soft historical lens blooming. "
            "Discovered lost history reel aesthetic."
        ),
        video_motion_prompt=(
            "vintage archival documentary shot with authentic mechanical camera movement, subtle film gate jitter, "
            "and realistic period reenactment motion. Preserve the archival 16mm film texture throughout."
        ),
        character_style_guidance=(
            "Characters look like real historical subjects captured in vintage archival footage: authentic period faces, "
            "unposed natural expressions, authentic heritage textiles and everyday wear."
        ),
        allow_real_media=True,
        film_look=True,
    ),
}

DEFAULT_STYLE = "realistic"


def get_style(name: str | None = None, strict: bool = False) -> VisualStyle:
    """Look up a visual style by name (case-insensitive slug).

    If strict=True, raises ValueError if the style name is unrecognized.
    Otherwise falls back to DEFAULT_STYLE.
    """
    if not name:
        return VISUAL_STYLES[DEFAULT_STYLE]
    normalized = name.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized not in VISUAL_STYLES:
        if strict:
            raise ValueError(f"Unknown visual style {name!r}. Must be one of: {', '.join(VISUAL_STYLES.keys())}")
        return VISUAL_STYLES[DEFAULT_STYLE]
    return VISUAL_STYLES[normalized]


def list_styles() -> list[VisualStyle]:
    """Return all registered visual styles."""
    return list(VISUAL_STYLES.values())


def style_names() -> list[str]:
    """Return the names of all registered visual styles."""
    return list(VISUAL_STYLES.keys())
