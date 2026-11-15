# Why real-time sampling of dynamic emissive textures matters: references and draft text (version 2)

Prepared 14 Nov 2026 for the TOG-26-0166 revision. This file replaces `motivation_references.md`: it contains everything from that file plus the third pass. Nothing in the paper was changed.

## How to read this

- Every quotation was copied from the source text itself (PDF, slides, web page or official documentation), except where a line is marked **[not read in full]**, **[abstract only]** or **[via summarizing tool]**. Check those before quoting.
- Section 1 says what is new. Section 2 is the draft text for the paper. Section 3 ranks the cases. Section 4 answers the question about the direction of light in virtual production. Section 5 gives the evidence per reference. Section 6 lists what I would leave out. Section 7 lists weak points a reviewer could raise. Section 8 describes the search and its limits. Section 9 is BibTeX.
- Three references are already in `sample-base.bib` and are reused with their existing keys: `bitterli2020spatiotemporal`, `binder2019radix`, `lu2013realtime`.

---

## 1. What is new in this version

1. **The virtual-production case now has the direction you asked for.** During the shoot the wall lights real actors, so no renderer has to sample it. A renderer has to light a synthetic subject with the wall's video in three other situations, and I found sources for each: before the shoot (prelight, previs and techvis), during the shoot (live composites with the camera frustum keyed out), and after it (computer-generated elements added to footage lit by the wall). Section 4 lays this out, with productions as examples: *Gravity*, *Rogue One*, *The Mandalorian*, *The Book of Boba Fett*, *House of the Dragon*.
2. **The virtual-production paragraph in section 2 is rewritten** around that argument. The other two paragraphs now include the additions from the second pass.
3. **The sweep of the venues that were incomplete is finished**: ISMAR, ISMAR-Adjunct, IEEE VR, I3D, SIGGRAPH and SIGGRAPH Asia Courses, Posters and Real-Time Live, and SIGGRAPH Asia conference papers. The total is now 41,522 unique records. It added little: three minor mixed-reality references and no change to the ranking.
4. **Bibliography gaps closed.** The three references that had no authors now have them, and two incomplete author lists are fixed (section 9).
5. **What I still did not find**: a peer-reviewed paper that simulates the light of an LED wall on a virtual subject with a path tracer, or any source that says such a simulation importance-samples the wall. The evidence for the pre-shoot case is trade press, a handbook and one SMPTE journal paper. The paragraph is worded so that the sampling claim is ours.

---

## 2. Draft paragraphs (LaTeX-ready)

Three paragraphs, one per community. They can replace or extend the second paragraph of the Introduction.

```latex
\paragraph{Real-time path tracing in games.}
Light sampling with spatiotemporal resampling draws its initial candidates from
tabulated distributions over emissive geometry and environment maps
\cite{bitterli2020spatiotemporal}, and the cost of rebuilding those tables is a known
obstacle to dynamic content. Wyman and Panteleev~\cite{wyman2021rearchitecting} report
that alias-table builds for large environment maps exceed 200\,ms, and replace them
with a structure that is rebuilt every frame precisely to allow ``truly dynamic
textured emissives, e.g., light probes streamed live from a 360 camera''. The quality
of these initial candidates still bounds the result: resampling is ``ultimately limited
by the quality of the initial candidates'' \cite{zeng2025restirpg}, and the integration
of ReSTIR in a shipped path-traced game lists initial candidate sampling quality among
its main sensitivities, with emissive surfaces and the skylight left to BSDF sampling
\cite{kozlowski2023cyberpunk}. Production engines report the same pressure from
content. Lumen lights scenes with emissive surfaces but notes ``a limit to how small
and bright those emissive areas can be without causing noise artifacts'', and names
explicit sampling of emissive meshes as future work \cite{wright2022lumen}; its
successor for direct lighting observes that artists now use rectangular and textured
lights ``a lot more'' \cite{narkowicz2025megalights}. Current guidance for path-traced
games recommends environment maps that are baked every frame so that dynamic skies and
clouds can be importance sampled, and a dedicated sampling structure for signs,
animated effects and procedural emissive materials \cite{nvidia2026ptwhitepaper}.
Recent work still describes the evaluation of many lights per pixel as a major
bottleneck of real-time rendering \cite{chen2026lightopt}.

\paragraph{Virtual production.}
On an LED stage the wall is at once the in-camera background and the light source of
the scene: the stage is driven as an image-based lighting instrument
\cite{debevec2002lighting,debevec2022dilation,legendre2022jointly}, and the video that
drives the wall also drives the lighting fixtures around it \cite{bengtsson2022ibl}.
While the camera rolls, the panels light the real actors physically. The rendering
problem appears whenever the subject under that light is synthetic, and this happens
at three points of a production. Before the shoot, the lighting of a volume is designed
in simulation: productions go through a prelight in the virtual art department, where
the engine reproduces the environment as it will appear on the screens
\cite{kadner2023stages,zwerman2023ves}, techvis rebuilds the on-set hardware as a 3D
scene \cite{failes2024hotd}, and digitized performers are previsualized inside the
virtual stage \cite{nash2025integration}. The practice is older than the LED volume:
for \emph{Gravity} the shots were previsualized and pre-lit digitally, and that
animation was then played on LED panels around the actors
\cite{seymour2013gravity,hamon2014gravity}; for \emph{Rogue One}, spherical images
rendered from the previs environments were shown on LED screens to light the actors
and the set \cite{bunish2017rogueone}. During the shoot, when a shot cannot be finished
in camera, the camera frustum is keyed and provisional imagery is composited live
while the rest of the wall keeps lighting the subjects \cite{kadner2021fieldguide}.
After the shoot, the creatures and environments of such shots are added in post
\cite{failes2022hotd} and have to match the lighting that the wall gave the actors.
Research has started to treat the wall accordingly, as a near-field, high-resolution
textured emitter whose image is known at every frame \cite{azzarelli2026relightable},
and to use LED stages to reproduce per-frame HDR environment maps at video rate
\cite{zhang2026pixelcube}. In all of these cases a renderer lights a synthetic subject
with a video, and its sampling structure has to follow that video frame by frame.

\paragraph{Mixed reality and telepresence.}
In augmented and mixed reality the illumination is not authored at all: it is captured
or estimated while the application runs. HDR environment maps are inferred from the
camera feed at interactive rates on mobile devices
\cite{legendre2019deeplight,somanath2021hdr,zhao2021xihe}, estimated consistently over
video \cite{li2023spatiotemporally,shen2025stglight,bolduc2026limo}, or taken directly
from a live $360^\circ$ stream with changing real-world lights
\cite{rhee2017mr360,rhee2018mr360live,walton2018dynamic}. For such high-frequency
illumination, importance sampling of the environment map is essential for efficient
rendering \cite{kronander2015photorealistic,alhakamy2020realtime}. Systems that do
path trace under a live panorama on a head-mounted display report that the result must
be denoised \cite{cheng2023environment,wu2024panoramic}, and that in a headset Monte
Carlo noise is more than a quality problem, since its temporal flicker aggravates
cybersickness \cite{taibo2024immersive}. Most real-time systems therefore avoid
sampling: they prefilter the map or reduce it to a few dominant lights, because, as
Saito et al.~\cite{saito2024relightable} state for photorealistic avatars on a VR
headset, existing relighting models are ``often too slow to render in real-time with
high-resolution continuous environments''. A sampling structure that can be rebuilt at
the rate of the display, and that is small enough to keep one per light, is a
precondition for moving these applications from prefiltered shading to path tracing
with correct shadows and interreflections.
```

Notes on these paragraphs:

- **Sentences that are our argument, not a source's**: the last sentence of each of the virtual-production and mixed-reality paragraphs; "The rendering problem appears whenever the subject under that light is synthetic"; and "have to match the lighting that the wall gave the actors". No cited source says that a prelight, a live composite or a post render importance-samples the wall, and none says that XR systems avoid Monte Carlo *because of* the per-frame build cost.
- **"importance sampling ... is essential"** is a statement of the Kronander survey. The Alhakamy survey is cited next to it as the newer survey of the field; I read only its abstract, so move that key to the previous sentence if you want the claim to rest on a text you can check.
- **"prefilter the map or reduce it to a few dominant lights"** is supported by Saito et al. (prefiltered mip lookup) and by MR360 (salient light detection). The MR360 detail comes from a talk abstract, so soften it to "prefilter the map" if you cannot check the paper.
- **"techvis rebuilds the on-set hardware as a 3D scene"**: the source says the techvis "involved creating a 3D virtual scene that replicated the on-set hardware". In that production the hardware was a motion-control camera and a motion base inside an LED volume; the sentence does not say the scene included the wall as a light.
- XR headsets run at 72 to 120 Hz; none of the cited papers gives that number in the passages I read, so the paragraph says "the rate of the display".
- The virtual-production paragraph is long (about 250 words). If space is short, cut the *Gravity* and *Rogue One* sentence first; it is the historical part.

---

## 3. The strongest cases, ranked

| # | Case | Lead references | Why it is strong |
|---|------|-----------------|------------------|
| 1 | Sampling-structure build cost blocks dynamic textured lights in real-time path tracing | Wyman and Panteleev 2021; Bitterli et al. 2020; RTXDI integration guide | States our exact problem, with a number (alias build over 200 ms) and our exact use case (live 360° probes). Published at HPG by the ReSTIR authors. |
| 2 | Initial light-sample quality limits ReSTIR | Zeng et al., SIGGRAPH Asia 2025; Kozlowski, SIGGRAPH 2023 course; Lin et al. 2026 | Answers "resampling will fix a poor sampler". Recent, SIGGRAPH venues. |
| 3 | Engines and artists are moving to emissive and textured lights | Wright et al. 2022 (Lumen); Narkowicz and Costa 2025 (MegaLights); NVIDIA 2026 whitepaper; Chen et al. 2026 | Three shipping-engine sources across four years, each naming noise or cost from emissive or textured lights. |
| 4 | LED walls are video-driven light sources rendered live | Debevec et al. 2002 (TOG); LeGendre et al. 2022; Debevec and LeGendre 2022; Bengtsson and Kang 2022; Zhang et al. 2026 (TOG) | Establishes the wall as an image-based light whose content changes per frame, with two TOG papers. Does not mention importance sampling. |
| 5 | Synthetic subjects are lit by the wall's video before, during and after the shoot (new) | Kadner 2023 (American Cinematographer); Seymour 2013 and Hamon et al. 2014 (*Gravity*); Bunish 2017 (*Rogue One*); Failes 2022 and 2024 (*House of the Dragon*); Kadner 2021 (field guide); Nash et al. 2025 (SMPTE journal); Azzarelli et al. 2026 | This is the direction that matches the method: a renderer lights a virtual subject with a video panel. Five named productions. Mostly trade press; none mentions sampling. |
| 6 | XR lighting is estimated or captured per frame, and path tracing under it is noisy | LeGendre et al. 2019; Somanath and Kurz 2021; Li et al. 2023 (TOG); Shen et al. 2025 (TOG); Rhee et al. 2017, 2018; Cheng et al. 2023; Wu and Wang 2024; Taibo and Iglesias-Guitian 2024 | A whole research line whose output is a new HDR environment map every frame, and three papers that tie it to Monte Carlo noise in a headset. |
| 7 | Real-time relighting under continuous environments is still too slow | Saito et al., CVPR 2024; Kronander et al. 2015 (Eurographics STAR) | Saito gives the "too slow" statement; the STAR gives the "importance sampling is essential" statement. |

Cases 1 to 3 mention sampling, noise or build cost directly. Case 6 mentions Monte Carlo noise but not the sampling structure. Cases 4, 5 and 7 establish that the dynamic light exists and that a renderer needs it; the link to sampling is ours. If you want six cases, merge 4 and 5 into one virtual-production case.

---

## 4. Virtual production: which way does the light go?

Your reading is right for the shoot itself. The engine renders an environment, the wall displays it, and the wall lights a real person. No light sampling is involved, because the light transport from wall to actor is physical. If the motivation rested only on that, a reviewer could object that the method solves a problem the stage does not have.

The method applies when the thing under the wall's light is virtual. The sources show five such situations.

| When | What happens | Real time? | Sources |
|------|--------------|------------|---------|
| Before the shoot: prelight | The virtual art department lights the scene and the stage in the engine before the stage is booked, with the cinematographer and a "virtual gaffer". | Yes (Unreal Engine, "instant feedback") | Kadner 2023; Failes 2020; Failes 2024; VES Handbook 2023 |
| Before the shoot: previs becomes the light | The previs animation is rendered as video and played on LED panels to light the actors. The final computer-generated shot is built around that lighting. | Playback yes; the content was pre-rendered | Seymour 2013 and Hamon et al. 2014 (*Gravity*); Bunish 2017 (*Rogue One*) |
| Before the shoot: performers inside the virtual stage | Digitized performers or virtual actors are placed in a model of the stage to plan the shot and its lighting. | Yes | Nash et al. 2025; Hendry et al. 2023; Deese 2022 |
| During the shoot: live composite | The camera frustum is turned green or blue, provisional imagery is composited into the viewfinder, and the rest of the wall keeps lighting the subjects. | Yes | Kadner 2021 (field guide); Failes 2022; Failes 2024 |
| After the shoot: final elements | Creatures and environments are rendered in post for footage whose actors were lit by the wall. | No (offline) | Failes 2022 (*House of the Dragon*); Seymour 2013 (*Gravity*); Failes 2020 (*The Mandalorian*) |

A sixth situation is research: papers that render or relight a subject under LED-wall or monitor video (Azzarelli et al. 2026; Zhang et al. 2026; Sengupta et al. 2021; Yeh et al. 2022; LeGendre et al. 2022).

What this supports and what it does not:

- **Supported:** lighting for LED stages is designed in simulation before the shoot, in a real-time engine; pre-rendered video has been used as the light source on set since 2013; computer-generated elements are composited live and in post into footage lit by the wall.
- **Not found:** a statement that any of these steps path-traces the scene or importance-samples the wall image. Prelight tools run on the engine's ordinary real-time lighting. The link is ours: these are renderers that light a synthetic subject with a video, and the trend on the wall side is toward ray and path tracing (Hill and Schulte 2023; Kadner 2024).
- **Mostly trade press.** Of the sources in this section only Hamon et al. 2014 (a one-page SIGGRAPH talk), Nash et al. 2025 (SMPTE journal), Deese 2022 (SMPTE conference) and the research papers are technical publications. The rest are American Cinematographer, fxguide, befores & afters, VFX Voice, Post Magazine, Epic's field guide and the VES handbook. TOG papers do cite such sources for production practice, but a reviewer may give them little weight.
- **The offline rows help less.** A post-production renderer has minutes per frame and can rebuild any table. The rows that matter for a real-time claim are the prelight, the previs of performers and the live composite.

---

## 5. Evidence per reference

### 5.1 Games and real-time path tracing

**Wyman and Panteleev, "Rearchitecting Spatiotemporal Resampling for Production", HPG 2021** (`wyman2021rearchitecting`)
- "Alias tables allow cheap O(1) sampling, which is vital with 64 million samples a frame. But optimal table builds cost O(N) [Vos91] and do not parallelize trivially on GPUs. In moderate complexity scenes CPU builders take under 0.5 ms, but build costs for large environment maps exceed 200 ms."
- "For dynamic light probes, we can substitute alternative approaches. Binder and Keller [BK19] propose one option, quickly building a radix forest to sample via the cutpoint method".
- "Building our hierarchy costs around 60 µs for a 2048×1024 light probe. Lookups are O(log N), but occur outside the inner loop, thanks to presampling. This allows truly dynamic textured emissives, e.g., light probes streamed live from a 360 camera."
- The teaser scene has "2001 analytic primitive lights and 453 emissive" lights in a "dynamic night city scene, rendered in a driving simulator in 31 ms".
- Read the caution in section 7 before using this one.

**Bitterli et al., "Spatiotemporal Reservoir Resampling...", TOG 2020** (already cited)
- "Importance sampling for both triangles and environment map locations is accelerated using an alias table [Walker ...]". When an environment map is present, 25% of the candidates are drawn from it.
- Scenes include "23,452 textured emissive triangles" (Subway) and "7,517 textured emissive triangles and a mostly-occluded environment map" (Burger Restaurant).

**Zeng et al., "ReSTIR PG: Path Guiding with Spatiotemporally Resampled Paths", SIGGRAPH Asia 2025** (`zeng2025restirpg`)
- "While ReSTIR significantly reduces variance through spatiotemporal resampling, its effectiveness is ultimately limited by the quality of the initial candidates, which are often poorly distributed and introduce correlation artifacts."
- "Yet if the initial samples are poor, a subset of high-energy samples can dominate the resampling process, known as sample impoverishment [Sawhney et al. 2024]."

**Kozlowski, "ReSTIR Integration in Cyberpunk 2077", in the SIGGRAPH 2023 course "A Gentle Introduction to ReSTIR"** (`kozlowski2023cyberpunk`, slides)
- Slide "ReSTIR Integration Insights": "Number of lights can have a big impact" on "Initial candidate sampling quality".
- Light domains: "Primitive lights (analytical)", "Mesh lights (emissives)", "Environment map (skylight)". For the shipped game: "Primitive lights - ReSTIR DI with uniform sampling" and "Emissives and skylight - BRDF sampling".
- Use: even the flagship path-traced game did not sample emissives or the sky explicitly in 2023.

**Lin, Kettunen and Wyman, "ReSTIR PT Enhanced", PACMCGIT 2026** (`lin2026restirptenhanced`)
- "For RIS of NEE samples (Section 6.1), we draw 32 light samples from the light tiles for NEE candidates at the primary hit, following Wyman and Panteleev [2021]."
- Use: 32 light candidates per pixel is the current practice. This matches the E37 measurement in the revision (32 candidates per pixel = 3.4 ms with BudgetLeafAlias against 15 to 30 ms with the 2D CDF).

**Wright, Narkowicz and Kelly, "Lumen: Real-time Global Illumination in Unreal Engine 5", SIGGRAPH 2022 Advances in Real-Time Rendering course** (`wright2022lumen`)
- "And emissive lighting, without artists needing to place individual light sources, although there is a limit to how small and bright those emissive areas can be without causing noise artifacts."
- "'The Matrix Awakens' has an experimental night mode, which is lit entirely with emissive meshes. Most of the lighting in this scene is coming from the small, bright light bulb meshes so handling their direct lighting through our GI method is an absolute stress test, as we're not explicitly sampling the light sources."
- Future work: "we'd like to have explicit sampling of emissive meshes in our downsampled radiance cache."

**Narkowicz and Costa, "MegaLights: Stochastic Direct Lighting in Unreal Engine 5", SIGGRAPH 2025 Advances course** (`narkowicz2025megalights`)
- "Artists also start to use complex light types (such as rect and textured lights) a lot more, so we need to make sure those are handled efficiently across the engine."
- "In particular, the logic to support rect and textured lights adds quite a bit of overhead, so we have specific shader permutations for those."
- "Small emissive surfaces or emissive surfaces which are far away, are really hard to find by just sampling the BRDF, even when augmented by Lumen (our GI/reflection system) ray guiding techniques."
- "Still stochastic light sampling isn't a magic bullet and light sources either reduce sampling pass performance or increase noise in the scene".

**NVIDIA, "Real-Time Path Tracing in Games: Best Practices for Performance and Scalability", whitepaper, June 2026** (`nvidia2026ptwhitepaper`)
- "Per-frame baked environment maps enable efficient importance sampling of dynamic sky and cloud lighting."
- "For dynamic sky lighting, generate a low-resolution environment map from procedural sky, atmosphere, clouds, moon, and sun-adjacent scattering. Use it for environment sampling, radiance-cache updates, and indirect-light queries".
- "For scenes with many emissive surfaces, maintain a separate emissive-light sampling structure alongside the main TLAS." It is "useful for many emissive surfaces and for lights that are difficult to track as explicit analytic lights, such as emissive meshes, signs, animated VFX emitters, or procedural emissive materials."
- Use: dynamic skies and clouds are a second gaming case that needs no video at all. Not peer reviewed.

**NVIDIA RTXDI SDK, Integration Guide** (`nvidia2024rtxdi`, documentation)
- "In order to use importance sampling for local lights and the environment map, their PDF textures and their mipmaps need to be built."
- "Local light PDF likely needs to be updated on every frame, if any lights change their intensities. Environment map PDF only needs to be updated when the environment map changes."
- On emissive materials: a triangle can "vary its radiance over time, depending on unpredictable shader math."

**Wyman et al., "A Gentle Introduction to ReSTIR", SIGGRAPH 2023 Courses** (`wyman2023restircourse`)
- "Our Amusement Park has over 3 million emissive triangles and just picking random light candidates took up to 25 milliseconds, without any fancy spatiotemporal reuse!"
- Use: candidate generation alone can exceed most of a frame; cost per light sample matters.

**Chen et al., "LightOpt: Lights Optimization for Real-time Rendering", SIGGRAPH 2026 Conference Papers** (`chen2026lightopt`)
- Abstract: "evaluating many lights per pixel remains a major performance bottleneck in real-time rendering"; the method is extended "to support Time-of-Day lighting." **[abstract only]**

**Coomans et al., "Real-time Rendering with a Neural Irradiance Volume", Computer Graphics Forum, 2026** (`coomans2026irradiance`)
- "real-time rendering requires light sources that can be efficiently sampled to avoid sampling noise."

**Coomans et al., "Real-time Rendering of Pre-integrated Neural Emitters", arXiv 2610.06762, 2026** (`coomans2026emitters`)
- Abstract: "Direct illumination from non-trivial emitters with occluding housing, high-polygon emissive meshes, spatially varying emission, or deformable assemblies is a persistent bottleneck in real-time rendering"; "pure sampling-based estimators need high sampling budgets to be noise-free". **[abstract only]** Preprint. It answers the problem by precomputing the emitter's illumination, which a video texture rules out.

**Freire and Pereira, "Dynamic Many-Light Importance Sampling for Real-Time Ray Tracing", WSCG 2024** (`freire2024dynamic`)
- Abstract: importance-sampling approaches that "build hierarchical data structures over all light sources" suffer "high maintenance costs for dynamic scenes". **[abstract only]** Minor venue; built on Falcor.

### 5.2 Virtual production: the wall as a video-driven light

**Debevec et al., "A Lighting Reproduction Approach to Live-Action Compositing", TOG 2002** (`debevec2002lighting`)
- Abstract: "each light can be set to an arbitrary color and intensity to replicate a real-world or virtual lighting environment." The origin of driving LEDs with images of a virtual set. **[abstract only]**

**Hamon et al., "Gravity: Motion Control and Face Integration", SIGGRAPH 2014 Talks** (`hamon2014gravity`)
- Cited by Debevec and LeGendre as the LED-panel form of the idea: actors lit by LED display panels showing the rendered environment. **[not read in full; one-page talk]**

**LeGendre, Lepicovsky and Debevec, "Jointly Optimizing Color Rendition and In-Camera Backgrounds in an RGB Virtual Production Stage", DigiPro 2022** (`legendre2022jointly`)
- "Beyond the in-camera background, an additional goal of filming inside an LED volume is to perform lighting reproduction, where individual light sources surrounding an actor are driven to reproduce the illumination of a given scene".
- The method optimizes separately "the pixels outside the camera's field of view illuminating the subjects".

**Debevec and LeGendre, "HDR Lighting Dilation for Dynamic Range Reduction on Virtual Production Stages", 2022** (`debevec2022dilation`)
- The stage has three purposes; the second is "To provide image-based lighting on the actors, illuminating them with images of the environments they are composited into".
- LED panels "often fall short as image-based lighting instruments due to limited dynamic range, making them unable to reproduce the brightness of concentrated light sources in a scene."
- Venue: the search result calls it a SIGGRAPH 2022 poster; I confirmed only the arXiv version (2205.07873). **Check the venue in the ACM DL.**

**Zhang et al., "Pixel Cube: Diffusion-based Portrait Video Relighting Through Realistic Lighting Reproduction", TOG 45(4), 2026** (`zhang2026pixelcube`)
- "LED stages are commonly used as virtual production systems in film making".
- "using per-frame high dynamic range (HDR) environment map as lighting control"; "our system can capture images lit up by the displayed environment at 60 FPS."
- Synthetic training data: "We use the MetaHuman plugin of Unreal Engine to render the synthetic data."
- Read through a summarizing tool, first 100k characters only. **Check the quotes against the PDF.**

**Azzarelli et al., "Relightable Gaussian Splatting for Virtual Production Using Image-Based Illumination", arXiv 2605.09024, 2026** (`azzarelli2026relightable`)
- "In-camera visual effects in virtual production (VP) use LED walls to provide both background imagery and image-based lighting."
- Environment maps "are typically low-resolution and assume far-field lighting. In VP, with near-field and high-resolution image-based lighting, this can lead to inaccurate results".
- Preprint, not peer reviewed as far as I could tell.

**Kadner, "Virtual World" (real-time ray tracing in virtual production), American Cinematographer, November 2024** (`kadner2024raytracing`)
- Path-traced environments on the wall "can be displayed at 24 fps and above"; "Richard could call for a lighting change in the background and it would happen instantaneously."; "Nvidia came up with a new type of AI de-noising for ray tracing".
- Trade press about Chaos Project Arena. Quotes obtained through a summarizing tool. **Check before quoting.**

**Hill and Schulte, "Lights, Camera, Interaction! The Real-Time Technology of ILM StageCraft", DigiPro 2023** (`hill2023stagecraft`)
- Covers the Helios renderer: direct lighting, ray-traced reflections, volumetrics. **[not read in full; title and scope from a search summary. Confirm title, authors and DOI in the ACM DL.]**
- Supporting, from Khronos (23 March 2021): "Industrial Light & Magic (ILM) recently introduced Vulkan Ray Tracing into their Helios real-time renderer."

**Epic Games, "In-Camera VFX Overview", Unreal Engine documentation** (`epic2024icvfx`)
- The outer frustum "turns the LED panels into a dynamic light and reflection source for the physical set."

**Lee and Luk, "Automated Lighting in Virtual Production using Real-Time Image Processing Technique", SIGGRAPH Asia 2025 Technical Communications** (`lee2025automated`)
- Maps the virtual environment, in real time, onto the studio lights around the volume. This is real-time reduction of a changing environment image to light sources. **[not read in full; from the DL abstract in a search result.]**

**Bengtsson and Kang, "Image Based Lighting - Current Capabilities and Limitations", SMPTE 2022 Media Technology Summit** (`bengtsson2022ibl`)
- Abstract: image-based lighting "has now evolved into principal photography lighting workflow where the LED video screens are augmented with traditional lighting fixtures, and the video content used to drive the LED video screens also drives the lighting fixtures." **[abstract only]** Engineering venue. The clearest statement found that video content is the light on set.

**Yu, George, Millward and Debevec, "Real-Time Multispectral Lighting Reproduction", SIGGRAPH 2025 Posters** (`yu2025multispectral`)
- Abstract as given by the SIGGRAPH history archive: "A real-time algorithm for driving multispectral LED lights in a spherical lighting reproduction stage to achieve accurate color rendition for a dynamic scene." **[abstract only, from a search result]** Optional; shows that lighting reproduction itself is now a real-time problem.

### 5.3 Virtual production: synthetic subjects under the wall's video (new)

These are the sources for section 4. Web articles were downloaded and the quotes copied from the page text, except where marked.

**Before the shoot: prelight and lighting simulation**

**Kadner, "The Virtual World: Stages of Color on The Book of Boba Fett", American Cinematographer, 3 January 2023** (`kadner2023stages`)
- "Productions destined for LED volumes must undergo a time-intensive prep in the virtual art department (VAD)", "where real-time animation tools such as Unreal Engine can facilitate robust, detailed lighting simulations."
- Felix Jorge (Narwhal Studios): "We do virtual prelights within the VAD and essentially create a LUT for each scene with the cinematographer".
- "The VAD can not only simulate the virtual environment as it will appear on the LED screens"; the sentence continues, by the tool's paraphrase, to say that it can also show the photometric values of real cinema lights inside the volume.
- "You're coloring during the virtual scouting and previs, before you even shoot".
- **[via summarizing tool; the site blocks direct download. The tool returned excerpts of at most 125 characters, so the first quote is two consecutive excerpts of one sentence. Read the article before quoting.]** URL: https://theasc.com/article/stages-of-color-book-of-boba-fett/

**Failes, "The Mandalorian and the Future of Filmmaking", VFX Voice, 1 April 2020** (`failes2020mandalorian`)
- "The beauty of all the sets being virtual was that they could be scouted in virtual reality", "In addition, they could 'pre-light' and adjust sets at this stage of production."
- "ILM did, however, build a matching Baby Yoda asset and worked on several CG character shots."
- **[via summarizing tool; check before quoting.]**

**Failes, "Motion bases, mo-co cameras and monofilament wires", befores & afters, 10 September 2024** (`failes2024hotd`), on *House of the Dragon* season 2
- "Pixomondo then re-worked the previs into techvis, which involved creating a 3D virtual scene that replicated the on-set hardware."
- Thompson (Pixomondo): "We worked closely with the director of photography and gaffers during pre-lighting to fine-tune the lighting on the LED walls, using a custom Unreal Engine setup for instant feedback."
- Einarsson (VFX supervisor): "You could eyeball it, but you need to have control over the buck, control over the camera and control over the world lighting."
- The techniques listed for the season include "incorporating interactive lighting from LED lighting panels, completing live composites".

**Zwerman and Okun (eds.), "The VES Handbook of Virtual Production", Focal Press, 2023** (`zwerman2023ves`)
- Chapter 7, "VAD (Virtual Art Department)", pp. 91-122, abstract: "Virtual scouting with production design using VR is laid out in an easy-to-follow manner, and VR-based pre-lighting and scene preparation is demonstrated in text and images."
- Chapter 22, "Art Department Integration in the Digital and Physical World", pp. 309-322, abstract: covers "lighting in the volume, preparing a virtual set for ICVFX, the pre-light".
- Chapter 23, "Lighting Types for Virtual Production (LED Volume)", pp. 323-344, abstract: "On-set image-based lighting is given detailed treatment".
- **[chapter abstracts only; the book is not open access. The index lists the editors, not the chapter authors.]** This is the reference work of the Visual Effects Society, so it is the most citable source for "prelight is standard practice".

**Dinur, "Real-time Rendering and Virtual Production", in The Filmmaker's Guide to Visual Effects, 2nd ed., Routledge, 2023** (`dinur2023realtime`)
- Abstract: "Virtual production completely upends the VFX timeline, as it basically shifts the work from post-production to pre-production." **[abstract only]** Optional.

**Before the shoot: previs becomes the light**

**Seymour, "Gravity: vfx that's anything but down to earth", fxguide, 8 October 2013** (`seymour2013gravity`)
- Tim Webber (VFX supervisor, Framestore): "We would do the previs, and then we would do the pre-light and then we would take the information from those two and do what we would call the techvis, which would be extracting it and changing the shot from what you see on the screen to what you would see in the studio, which would often look totally different."
- "The light box consisted of a large array of LEDs - essentially like an inward facing screens of giant television screens."
- "As its name suggests, the purpose of the light box was to cast the appropriate illumination on the actors inside, no matter where they were or how fast they were moving in relation to the light source."
- "The lightbox solution that was used in London worked from less of a principle of re-lighting (as in the Eurographics 2011 approach) and more from the position of creating light environments that were solved from pre-production previs."
- "The interior walls were constructed of 196 panels, each measuring approximately 2 feet by 2 feet and each holding 4,096 tiny LED lights."
- Thirteen years old, over the limit you set, but it is the origin of the workflow and it has an ACM companion (next entry).

**Hamon et al. 2014** (`hamon2014gravity`, listed in 5.2) is the ACM record of the same production. The DOI registry gives its title as "Gravity" only; check the full title in the ACM DL.

**Framestore, "Preparing Gravity", 23 October 2023** (not in the BibTeX; a company news page)
- "I worked closely with DOP Emmanuel 'Chivo' Lubezki on the lighting design and the digital pre-light of the previs that would guide our lighting on set." The page text I extracted does not make the speaker clear.

**Bunish, "Cover Story: Rogue One: A Star Wars Story", Post Magazine, 1 January 2017** (`bunish2017rogueone`)
- "The Third Floor created footage to project onto massive LED screens when the actors were inside any spaceship."
- Barry Howell (previs supervisor, The Third Floor): "We customized a plug-in that allowed us to create a 4K 360-degree spherical image using our previs environments", "We could provide these to ILM for projection on the LED screens through TouchDesigner. As the environments almost encapsulated the actors, it was possible to light them and the set with proper lighting and color temperature so the plates would integrate well with the final composites."
- Sumner (ILM): "When they were shooting the cockpit on a gimbal, we pre-rendered a number of sequences that were played back on an array of LED panels for natural, interactive lighting on the environment and the actors".
- Use: the light source on set was a pre-rendered 360° video, and the final composite had to integrate with it. This is a video environment map used as a light, in production, nine years ago.

**Before the shoot: performers inside the virtual stage**

**Nash et al., "Integration of Depth and Volumetric Capture Workflows for 2.5D Virtual Production", SMPTE Motion Imaging Journal 134(6), 2025** (`nash2025integration`)
- Abstract: a 2.5D asset of a performer, made from one video, "is then loaded into Disguise Designer for pre-visualisation of the performers within the virtual stage." **[abstract only]** Peer-reviewed journal. The abstract does not say how the performers are lit.

**Hendry et al., "Simulate This! Virtual Production and Cinematic Education with cineDESK", AVANCA | CINEMA, 2023** (`hendry2023cinedesk`)
- Abstract: "a simulation tool to facilitate the previsualization of film scenes"; users "explore how space, light, props and acting are translated into cinematic sequences", including "lighting, production design elements and even the appearance of their (virtual) actors." **[abstract only]** Minor venue.

**Deese, "Unreal Savings: Budget Previs/Techvis for Student Films", SMPTE 2022 Media Technology Summit** (`deese2022unreal`)
- Abstract: filmmakers "recreated filming locations within video game engines to technically and accurately plan lighting, camera placement and movement, as well as the arrangement of actors on set before filming even begins." **[abstract only]** Not about LED walls; shows that lighting is planned in a game engine before the shoot even on small productions.

**During the shoot: live composites**

**Kadner, "The Virtual Production Field Guide, Volume 2", Epic Games, 2021** (`kadner2021fieldguide`)
- "Live compositing can also be complementary to LED wall cinematography. A production may determine a specific shot is too complicated or is not ready to be captured in camera on the day. In this case, the camera frustum can be turned green to composite provisional footage into the camera viewfinder and monitor. The interactive lighting from the area outside of the frustum still enhances the subjects."
- On *The Mandalorian*: green-screen halos placed behind the actors "gave the filmmakers the flexibility of a clean green screen for post compositing, while still preserving the interactive lighting from the non-green-screen portion of the frame."
- "Techvis is used to work out the precise technical requirements of practical and digital shots before committing to crew and equipment on the production day."
- "In the new, real-time paradigm, previs can now be thought of as the beginning of production."
- Jon Favreau, on shooting a person in front of a green screen: "Now, that human is going to be talking to a CG character and it's going to inherit that lighting." He is describing green-screen work there, not the LED wall, so use it only for the general point that added characters inherit the lighting of the plate.
- Published by a vendor, written by the same journalist as the American Cinematographer articles. Widely cited in the virtual-production literature.

**After the shoot: final elements for footage lit by the wall**

**Failes, "Motion bases and making mayhem, in the volume", befores & afters, 1 December 2022** (`failes2022hotd`), on *House of the Dragon* season 1
- The sequence was "heavily previsualized by The Third Floor and then set up for filming on the LED wall 'V' stage at Leavesden, where actors rode a pre-programmed motion base against virtual environments built by Pixomondo (which also crafted the final dragon animation and visual effects)."
- Angus Bickerton (VFX supervisor): "Once we were getting into the mood of things and started to get the feel right, then we would do takes with blue in the inner frustum. We would have the interactive environment in the outer frustum, but we've got blue in the camera frustum."
- "Now it's still that, but also the fact that you're getting great interactive light, the actors and crew kind of experience the sequence on set and you're getting the benefit of that."

**Abrams, interview with cinematographer Vanja Cernjul, Motion Picture Association "The Credits", 13 June 2025** (not in the BibTeX; supporting)
- "We shot these sequences inside a Volume, surrounded by large LED screens creating a near-360-degree animated sky. These weren't used as background plates but as dynamic lighting sources."
- "The buck is custom-built and pre-programmed to move in sync with the dragon's flight path based on VFX previsualization."

**Research that renders or relights a subject under screen video**

**Azzarelli et al. 2026** (above): the method relights a captured scene for new LED-wall content after the shoot. Its introduction states the motivation: the "tight coupling between background imagery and lighting at capture time limits post-production flexibility", and one of its datasets "uses an LCD monitor as the primary light source".

**Sengupta et al., "A Light Stage on Every Desk", ICCV 2021** (`sengupta2021lightstage`)
- "Every time you sit in front of a TV or monitor, your face is actively illuminated by time-varying patterns of light."
- "Our key insight is that the simple act of watching video on a monitor or TV sends patterns of light across your face."
- A capture method, not a renderer. It is the plainest statement in the literature that ordinary video on a screen is a time-varying light source. I left it out in version 1; with the argument now resting on screens as lights, it is worth one citation.

**Yeh et al., "Learning to Relight Portrait Images via a Virtual Light Stage and Synthetic-to-Real Adaptation", TOG 41(6), 2022** (`yeh2022virtuallightstage`)
- Abstract: replaces light-stage capture with synthetic humans rendered under environment maps to train a relighting network. **[abstract only]** Together with Pixel Cube (synthetic data rendered in Unreal Engine) and Li et al. 2023 (360K environment maps, path traced), this is the dataset-generation use: a renderer that must light subjects under very many distinct environment maps.

**Clausen et al., "Fitting Spherical Gaussians to Dynamic HDRI Sequences", SIGGRAPH Asia 2024 Posters** (`clausen2024fitting`)
- Abstract: "a technique for fitting high dynamic range illumination (HDRI) sequences using anisotropic spherical Gaussians (ASGs) while preserving temporal consistency in the compressed HDRI maps." **[abstract only]** From Debevec's group at Netflix Eyeline. It shows that sequences of HDR environment maps are a working data type in production research, and that the current answer is to compress them to a few lobes, not to sample them.

**LeGendre et al. 2022** (above) also simulates before it shoots: from calibration data, the paper computes how a colour chart will appear under the stage's LEDs. It is a colour simulation of the stage, not a rendering of a scene.

### 5.4 Mixed reality, AR and telepresence

**LeGendre et al., "DeepLight: Learning Illumination for Unconstrained Mobile Mixed Reality", CVPR 2019** (`legendre2019deeplight`)
- "our network runs at interactive frames rates on a mobile device, and, when used in combination with real-time rendering techniques, enables more realistic mobile mixed reality composites." (The typo "frames rates" is in the original.)

**Somanath and Kurz, "HDR Environment Map Estimation for Real-Time Augmented Reality", CVPR 2021** (`somanath2021hdr`)
- "We present a method to estimate an HDR environment map from a narrow field-of-view LDR camera image in real-time."
- "a mobile application that is able to run our neural network model in under 9 ms on an iPhone XS, and render in real-time, visually coherent virtual objects in previously unseen real-world environments."

**Zhao and Guo, "Xihe: A 3D Vision-based Lighting Estimation Framework for Mobile Augmented Reality", MobiSys 2021** (`zhao2021xihe`)
- Provides "accurate omnidirectional lighting estimation in real time" and "takes as fast as 20.67ms per lighting estimation".

**Li et al., "Spatiotemporally Consistent HDR Indoor Lighting Estimation", TOG 2023** (`li2023spatiotemporally`)
- "when the input is a video sequence, our framework can progressively refine" the lighting; it "preserves temporal consistency"; target is "photorealistic AR applications such as object insertion."
- The method contains "an in-network Monte-Carlo rendering layer".
- Training data: "around 360K HDR environment maps of much higher resolution and 38K video sequences, rendered with GPU-based path tracing." This is a side case: dataset generation renders under hundreds of thousands of distinct environment maps, so per-map build cost adds up there too.

**Bolduc et al., "Lighting in Motion: Spatiotemporal HDR Lighting Estimation", CVPR 2026** (`bolduc2026limo`)
- "LIMO can readily be used in virtual production (right), for instance by inserting actors captured in light domes in real sets."
- "Whether the task is to composite an actor into an environment or add an object to an image sequence, having access to accurate lighting information is critical."
- Co-authored by Debevec; links cases 4 and 5.

**Rhee et al., "MR360: Mixed Reality Rendering for 360° Panoramic Videos", IEEE TVCG 23(4), 2017** (`rhee2017mr360`)
- Abstract, via a library record: the pipeline "does not require any pre-computation", so it can "synthesize an interactive MR scene from a live 360-video stream". **[paper not read; paywalled.]**

**Rhee et al., "Mixed Reality 360 Live", SIGGRAPH 2018 Real-Time Live!** (`rhee2018mr360live`)
- "A live demo for real-time image-based lighting, light detection, mixed reality rendering, and composition of 3D objects into a live-streamed 360° video of a real-world environment with dynamically changing real-world lights is shown."

**Kronander et al., "Photorealistic Rendering of Mixed Reality Scenes", Computer Graphics Forum 34(2), Eurographics 2015 STAR** (`kronander2015photorealistic`)
- "For scenes with high frequency illumination, importance sampling of the environment map is essential for efficient rendering of diffuse surfaces [PH10]."
- Section 4.2, Temporally varying IBL: "Synthetic objects composited into real world video footage also benefit from temporally consistent and accurate illumination. Capturing a light probe at video frame rates, however, poses a different set of challenges".
- It reviews Havran et al. 2005 and Wan et al. 2005, 2011 (all already cited in the paper) as the methods for dynamic environment maps. Eleven years old, slightly over the limit you set, but it is the survey of the field.

**Saito et al., "Relightable Gaussian Codec Avatars", CVPR 2024** (`saito2024relightable`)
- "existing relighting models are limited in fidelity and often too slow to render in real-time with high-resolution continuous environments."
- "this synthesis typically needs to be performed in real-time for primary applications of photorealistic avatars including games and telecommunication".
- "the real-time requirement severely limits the algorithmic design."
- Their workaround: "prefiltering the environment maps ... This requires only a single mipmap texture look up per 3D Gaussian, which is a critical property for real-time relighting with all-frequency reflections."
- "We also demonstrate real-time relighting of avatars on a tethered consumer VR headset".

**Cheng et al., "Realistic Volume Rendering with Environment-Synced Illumination in Mixed Reality", ISMAR-Adjunct 2023** (`cheng2023environment`)
- "The dynamic HDR environment illumination is first estimated consecutively from panoramic images captured using an LDR panorama camera in real-time."
- A denoiser is then needed "to optimize the DVR results with panoramic HDR illumination."
- Use: a headset application that path-traces under a live panorama and has to fight the noise.

**Wu and Wang, "Panoramic Ray Tracing for Interactive Mixed Reality Rendering Based on 360° RGBD Video", IEEE CG&A 44(1), 2024** (`wu2024panoramic`)
- Abstract: "an irradiance estimation channel is introduced to generate noisy Monte Carlo images", then filtered, to produce "frames for dynamic virtual objects in 360° RGBD videos in real time". **[abstract only]**
- A two-page precursor exists: Wu, Wang and Ke, "Interactive Panoramic Ray Tracing for Mixed 360° RGBD Videos", IEEE VR Workshops 2023, DOI 10.1109/VRW58643.2023.00231. Cite the journal version.

**Taibo and Iglesias-Guitian, "Immersive 3D Medical Visualization in Virtual Reality using Stereoscopic Volumetric Path Tracing", IEEE VR 2024** (`taibo2024immersive`)
- "in VR the interaction never stops, and those techniques are not directly applicable to head-tracked environments as the temporal flicker introduced by MC noise would significantly increase the cybersickness symptoms".
- Use: in a headset, noise costs more than image quality.

**Walton and Steed, "Dynamic HDR Environment Capture for Mixed Reality", VRST 2018** (`walton2018dynamic`)
- Abstract: "capturing and updating a HDR radiance map of the real environment ... in real time", to "render convincing virtual objects whose illumination changes dynamically to reflect the changing real environment around them." **[abstract only]**

**Shen et al., "STGlight: Online Indoor Lighting Estimation via Spatio-Temporal Gaussian Fusion", TOG 44(6), 2025** (`shen2025stglight`)
- Abstract: processes "a stream of LDR RGB-D video frames", "enabling the prediction of HDR environment maps at arbitrary locations for each frame"; earlier methods restrict "applications such as compositing animated models into videos." **[abstract only]** A second, newer TOG paper for this case.

**Alhakamy and Tuceryan, "Real-time Illumination and Visual Coherence for Photorealistic Augmented/Mixed Reality", ACM Computing Surveys 53(3), 2020** (`alhakamy2020realtime`)
- A 34-page survey of "dynamic and real-time illumination measurement, estimating, and rendering of augmented reality scenes". **[abstract only]** Newer than the Kronander STAR.

**Tarko, Tompkin and Richardt, "Real-time Virtual Object Insertion for Moving 360° Videos", VRCAI 2019** (`tarko2019realtime`)
- Abstract: recovers "high dynamic range environment maps which vary spatially along the camera path" and renders in Unity "with dynamic lighting, image-based shadowing". **[abstract only]** The same work appeared as a two-page IEEE VR 2019 abstract ("OmniMR", DOI 10.1109/VR.2019.8798067); cite one.

---

## 6. Candidates I would leave out

| Candidate | Reason |
|-----------|--------|
| James et al., "Colour-Managed LED Walls", SIGGRAPH 2021 Talks | About colour calibration. Says nothing on lighting or rendering cost. LeGendre 2022 covers the same ground and does mention lighting. |
| Li et al., "URAvatar", SIGGRAPH Asia 2024 | Same point as Saito 2024, weaker wording ("without expensive ray tracing"). One avatar paper is enough. |
| Zhao et al., "LitAR", IMWUT 2022 | Real-time environment maps for AR reflections. Duplicates Xihe and EnvMapNet. |
| Majercik et al., "Scaling Probe-Based Real-Time Dynamic GI for Production", JCGT 2021 | Shows a scene lit mostly by emissive monitor screens, but handles them through probes, with no sampling discussion. |
| Ray Tracing Gems II, ch. 39 (Morrical and Zellmann) | Already cited in the paper. |
| RelightVid, Lux Post Facto, CamLit and other video-diffusion relighting papers | They take per-frame HDR maps as conditioning, not as lights in a renderer. The link to sampling is too indirect. |
| Epic "Speed of Light" demo, SIGGRAPH 2018 | First real-time "animated textured area lights with ray-traced soft shadows". Only blog sources; eight years old. |
| Seymour, "Art of (LED wall) virtual production sets, part two", fxguide 2020 | Describes digital light cards on the wall. Useful background, but it is the wall lighting real actors again. |
| Sancho et al., "Neural Render Proxies for Interactive and Differentiable Lighting", EGSR 2026 (Disney Research) | Interactive lighting design for production scenes. It notes that its method "does not benefit from illumination-aware techniques such as next event estimation", so it argues around light sampling, not for it. |
| Sophia-in-Audition (2024), "Virtually Being" (SIGGRAPH Asia 2025) | Use the term virtual production for light-dome capture and for video generation. No rendering under wall light. |
| ASC StEM3 test material, the open-source "virtual-led-volume" course project, set.a.light 3D, disguise and Pixotope product pages | Tools and vendor pages. None states that the wall is simulated as a light on virtual subjects. |
| ILM and Lux Machina patents on LED-stage lighting | Patents; describe placing virtual lights that the camera does not see. Not citable as evidence of practice. |
| OmniMR (IEEE VR 2019), Wu, Wang and Ke (IEEE VR Workshops 2023) | Two-page versions of Tarko 2019 and Wu and Wang 2024, which are listed. |

Groups screened and rejected in bulk:

- **Real-time streaming video relighting** (LiveLight, TOG 2026; LightShift, SIGGRAPH Asia 2026 Real-Time Live; EdgeRelight360, CVPR Workshops 2024; Real-Time 3D-Aware Portrait Video Relighting, CVPR 2024). Strong 2024 to 2026 interest in relighting video in real time, but learned image-to-image methods with no renderer and no light sampling.
- **Relightable avatars** (about twenty papers, 2023 to 2026). All prefilter or use spherical harmonics. Saito 2024 remains the best single citation.
- **Real-time global illumination** (DDGI variants, radiance caches, neural GI; about forty papers). They treat emissive surfaces through probes or caches and do not discuss sampling them.
- **Many-light methods** (stochastic lightcuts, lighting grid hierarchy, Disney's cache points). Relevant to light selection across many lights, not to sampling within one textured light.
- **Lighting estimation from single images** (about sixty papers). Not per-frame; DeepLight, EnvMapNet, Xihe, Li 2023 and STGlight cover the video-rate case.
- **Virtual production in SMPTE and DigiPro** (about thirty records). Colour management, acoustics, pipelines and sustainability. None on rendering cost or sampling apart from the items listed.
- **ISMAR, ISMAR-Adjunct and IEEE VR, full sweep** (4,655 records). Mixed-reality lighting papers there use spherical harmonics, point-light estimation or differential rendering with shadow maps. The path-tracing ones are already listed (Cheng 2023; Wu and Wang 2024; Taibo and Iglesias-Guitian 2024).
- **SIGGRAPH and SIGGRAPH Asia Courses, Posters and Real-Time Live** (1,917 records). Nothing on sampling dynamic lights beyond the courses already cited and the Clausen poster.

---

## 7. Weak points a reviewer could raise

1. **Wyman and Panteleev cut both ways.** The same passage that gives the 200 ms alias-build figure also says their mip hierarchy is built in "around 60 µs for a 2048×1024 light probe". So that paper supports "per-texel alias tables cannot be rebuilt per frame", and does not support "no existing structure can be built per frame". The argument for LeafAlias against a mip hierarchy has to rest on cost per sample (their lookups are O(log N), and they hide them by presampling) and on memory per light, which is where the revision's own measurements point.
2. **Virtual production sources do not mention sampling.** They establish that the wall is a per-frame image-based light, that its lighting is designed in simulation beforehand, and that synthetic elements are composited into footage it lit. The step to "a renderer must importance-sample it per frame" is ours.
3. **During the shoot the stage does not need the method.** The wall lights real people. A reviewer who knows the workflow will say so. Section 4 and the rewritten paragraph answer this by naming the situations where the subject is synthetic; the real-time ones are the prelight, the previs of performers and the live composite.
4. **Prelight tools do not path trace today.** They run on the engine's real-time lighting. The claim that they would benefit from importance sampling of the wall rests on the general trend toward path tracing in these engines (cases 1 to 3), not on a statement by a virtual-production source.
5. **The pre-shoot evidence is mostly trade press.** Technical publications in that group: Hamon et al. 2014, Nash et al. 2025, Deese 2022, Bengtsson and Kang 2022. Keep the trade sources to the few that carry a named production, or move them to a footnote.
6. **XR and avatar systems use prefiltering, not sampling.** They show demand for real-time lighting from dynamic environment maps. A reviewer can answer that prefiltering works for them. The reply is that prefiltering gives no shadows or interreflections, which is the reason the STAR calls importance sampling essential, and that the systems which do path trace report noise.
7. **Several sources are not peer reviewed**: the two Advances course talks, the ReSTIR course slides, the NVIDIA whitepaper and RTXDI guide, the Epic documentation and field guide, the Khronos note and the trade articles. Course material is normal to cite in TOG; I would keep the whitepaper, documentation and trade press to a minimum.
8. **Items not read in full** are marked in section 5. The ones the draft paragraphs lean on: Kadner 2023 (through a summarizing tool), the VES Handbook (chapter abstracts), Nash et al. 2025, Bengtsson and Kang 2022, Wu and Wang 2024, Shen et al. 2025, Alhakamy and Tuceryan 2020, Walton and Steed 2018, Chen et al. 2026 (abstracts), Hamon 2014, Rhee 2017, Debevec 2002.
9. **Frame rates.** The paper uses 30 fps. The LED-stage sources give 24 fps (camera) and 60 fps (Pixel Cube capture); XR sources give per-estimate times of 9 to 21 ms. None contradicts the 33 ms budget, and the XR case is stricter.
10. **Consistency with the measured results.** The revision's own data supports modest gains (equal quality reached 1.15 to 1.5 times faster, about 3 times on an 8K wall, and a lower cost per light sample). The motivation text argues that the problem matters; it should not be read as promising more than that.

---

## 8. How the search was done, and its limits

**First pass (targeted reading).** About 50 web searches and about 25 PDFs and slide decks read, with quotations copied from the text.

**Second pass (bulk screening).** Metadata and abstracts for 30,127 unique records, 2015 to 2026: a sweep by venue of ACM TOG (3,550 records), IEEE TVCG (5,414), Computer Graphics Forum (3,351), The Visual Computer, Computers & Graphics, IEEE CG&A, SMPTE Motion Imaging Journal, PACM CGIT, SIGGRAPH conference papers, SIGGRAPH Talks, SIGGRAPH Asia Technical Communications and DigiPro; 50 keyword searches across all venues; and a second index for CVPR, ICCV, ECCV, NeurIPS, 3DV, EGSR, HPG and Eurographics. Each record was scored on title and abstract for the combination light source + dynamic content + sampling, noise or real time. I read the top 490 or so titles and about 30 abstracts, and searched 473 open-access PDFs sentence by sentence.

**Third pass (this version).**

- Venue sweep completed for the venues that were cut short: ISMAR (1,263 records), ISMAR-Adjunct (1,420), IEEE VR (1,972), I3D (146), SIGGRAPH Courses (227), SIGGRAPH Asia Courses (156), SIGGRAPH Posters (667), SIGGRAPH Asia Posters (706), Real-Time Live (161 across both conferences), SIGGRAPH Asia conference papers 2022 to 2025 (521). SIGGRAPH Asia papers before 2022 were journal papers and are in the TOG sweep.
- Thirty new keyword searches aimed at the virtual-production question (previs, prelight, techvis, digital twin of a stage, LED wall as light, display as light source, video-textured area lights, stage and concert visualization), and three broad searches of the second index.
- 11,395 new unique records, for a total of **41,522**. The whole set was scored again with a second key for virtual production, previs and screens as light sources. I read about 500 more titles and about 45 abstracts.
- Full text: 564 more open-access records tried, 262 readable PDFs, no new usable passage.
- About 20 more web searches and 12 articles or documents read for section 4.

Limits:

- **Screening is by title and abstract.** A paper that mentions the problem only in its body, and is not open access, is missed. About 30% of the records in the second pass had no abstract and were screened by title only.
- **Full text was searched for about 735 papers only.** Most graphics papers are behind publisher walls or have no open-access link in the index.
- **Conference coverage depends on the index.** EGSR and HPG papers appear mostly under Computer Graphics Forum and PACM CGIT. Some proceedings years return no records under their venue identifier; the keyword searches are the only cover for those.
- **Trade press is not indexed.** The sources of section 4 came from web searches, which find what is popular and well linked. There may be better production examples that I did not find.
- **"None found" is not "none exists".** I found no direct successor after 2015 to the already-cited work on sampling dynamic environment maps (Havran 2005, Wan 2005 and 2011, Lu 2013, Kronander 2014) other than your own 2026 poster, and no paper that path-traces a virtual subject under an LED wall.

The outcome of the bulk passes in one sentence: nothing in 41,522 records states the problem more directly than Wyman and Panteleev 2021, and the ranking of the cases did not change.

---

## 9. BibTeX

Fields marked `% CHECK` were not confirmed against the publisher record. Keys changed since version 1: `vr2024volumetric` is now `taibo2024immersive`, `cgf2026neuralirradiance` is now `coomans2026irradiance`, `arxiv2026neuralemitters` is now `coomans2026emitters`.

```bibtex
@inproceedings{wyman2021rearchitecting,
  author    = {Wyman, Chris and Panteleev, Alexey},
  title     = {Rearchitecting Spatiotemporal Resampling for Production},
  booktitle = {High-Performance Graphics - Symposium Papers},
  year      = {2021},
  pages     = {23--41},
  publisher = {The Eurographics Association},
  doi       = {10.2312/hpg.20211281}
}

@inproceedings{zeng2025restirpg,
  author    = {Zeng, Zheng and Kettunen, Markus and Wyman, Chris and Wu, Lifan and Ramamoorthi, Ravi and Yan, Ling-Qi and Lin, Daqi},
  title     = {{ReSTIR PG}: Path Guiding with Spatiotemporally Resampled Paths},
  booktitle = {SIGGRAPH Asia 2025 Conference Papers},
  year      = {2025},
  publisher = {ACM},
  doi       = {10.1145/3757377.3763813}
}

@article{lin2026restirptenhanced,
  author  = {Lin, Daqi and Kettunen, Markus and Wyman, Chris},
  title   = {{ReSTIR PT} Enhanced: Algorithmic Advances for Faster and More Robust {ReSTIR} Path Tracing},
  journal = {Proceedings of the ACM on Computer Graphics and Interactive Techniques},
  year    = {2026},
  doi     = {10.1145/3804494}
  % CHECK volume and issue
}

@inproceedings{wyman2023restircourse,
  author    = {Wyman, Chris and Kettunen, Markus and Lin, Daqi and Bitterli, Benedikt and Yuksel, Cem and Jarosz, Wojciech and Kozlowski, Pawel and De Francesco, Giovanni},
  title     = {A Gentle Introduction to {ReSTIR}: Path Reuse in Real-Time},
  booktitle = {ACM SIGGRAPH 2023 Courses},
  year      = {2023},
  publisher = {ACM},
  doi       = {10.1145/3587423.3595511},
  url       = {https://intro-to-restir.cwyman.org/}
}

@misc{kozlowski2023cyberpunk,
  author       = {Kozlowski, Pawel and De Francesco, Giovanni},
  title        = {{ReSTIR} Integration in {Cyberpunk 2077}},
  howpublished = {In ACM SIGGRAPH 2023 Courses: A Gentle Introduction to ReSTIR},
  year         = {2023},
  url          = {https://intro-to-restir.cwyman.org/presentations/2023ReSTIR_Course_Cyberpunk_2077_Integration.pdf}
}

@misc{wright2022lumen,
  author       = {Wright, Daniel and Narkowicz, Krzysztof and Kelly, Patrick},
  title        = {Lumen: Real-time Global Illumination in {Unreal Engine 5}},
  howpublished = {ACM SIGGRAPH 2022 Courses: Advances in Real-Time Rendering in Games},
  year         = {2022},
  url          = {https://advances.realtimerendering.com/s2022/}
}

@misc{narkowicz2025megalights,
  author       = {Narkowicz, Krzysztof and Costa, Tiago},
  title        = {{MegaLights}: Stochastic Direct Lighting in {Unreal Engine 5}},
  howpublished = {ACM SIGGRAPH 2025 Courses: Advances in Real-Time Rendering in Games},
  year         = {2025},
  url          = {https://advances.realtimerendering.com/s2025/}
}

@misc{nvidia2026ptwhitepaper,
  author       = {{NVIDIA}},
  title        = {Real-Time Path Tracing in Games: Best Practices for Performance and Scalability},
  howpublished = {Whitepaper},
  year         = {2026},
  month        = jun,
  url          = {https://github.com/NVIDIA-RTX/Whitepapers/tree/main/pt_performance_whitepaper}
}

@misc{nvidia2024rtxdi,
  author       = {{NVIDIA}},
  title        = {{RTXDI} Integration Guide},
  howpublished = {RTX Dynamic Illumination SDK documentation},
  year         = {2024},
  url          = {https://github.com/NVIDIA-RTX/RTXDI/blob/main/Doc/Integration.md}
  % CHECK year of the version you cite
}

@article{debevec2002lighting,
  author  = {Debevec, Paul and Wenger, Andreas and Tchou, Chris and Gardner, Andrew and Waese, Jamie and Hawkins, Tim},
  title   = {A Lighting Reproduction Approach to Live-Action Compositing},
  journal = {ACM Transactions on Graphics},
  volume  = {21},
  number  = {3},
  pages   = {547--556},
  year    = {2002},
  doi     = {10.1145/566654.566614}
}

@inproceedings{hamon2014gravity,
  author    = {Hamon, Pierre-Lo{\"\i}c and Harmer, James and Penn, Stuart and Scapel, Nicolas},
  title     = {Gravity: Motion Control and Face Integration},
  booktitle = {ACM SIGGRAPH 2014 Talks},
  year      = {2014},
  articleno = {35},
  doi       = {10.1145/2614106.2614193}
  % CHECK full title: the DOI registry lists it as "Gravity"
}

@inproceedings{legendre2022jointly,
  author    = {LeGendre, Chloe and Lepicovsky, Lukas and Debevec, Paul},
  title     = {Jointly Optimizing Color Rendition and In-Camera Backgrounds in an {RGB} Virtual Production Stage},
  booktitle = {Proceedings of the 2022 Digital Production Symposium (DigiPro '22)},
  year      = {2022},
  publisher = {ACM},
  note      = {arXiv:2205.12403}
  % CHECK DOI
}

@inproceedings{debevec2022dilation,
  author    = {Debevec, Paul and LeGendre, Chloe},
  title     = {{HDR} Lighting Dilation for Dynamic Range Reduction on Virtual Production Stages},
  booktitle = {ACM SIGGRAPH 2022 Posters},
  year      = {2022},
  note      = {arXiv:2205.07873}
  % CHECK venue (poster) and DOI
}

@article{zhang2026pixelcube,
  author    = {Zhang, Yufan and Ji, Yu and Ajiboye, Ayo and Wu, Rundi and Guo, Yu and Zheng, Changxi and Ye, Jinwei},
  title     = {Pixel Cube: Diffusion-based Portrait Video Relighting Through Realistic Lighting Reproduction},
  journal   = {ACM Transactions on Graphics},
  volume    = {45},
  number    = {4},
  articleno = {119},
  year      = {2026},
  doi       = {10.1145/3811400}
}

@misc{azzarelli2026relightable,
  author       = {Azzarelli, Adrian and Anantrasirichai, Nantheera and Pollock, James and Bull, David R.},
  title        = {Relightable {Gaussian} Splatting for Virtual Production Using Image-Based Illumination},
  howpublished = {arXiv:2605.09024},
  year         = {2026}
}

@article{kadner2024raytracing,
  author  = {Kadner, Noah},
  title   = {Virtual World},
  journal = {American Cinematographer},
  year    = {2024},
  month   = nov,
  url     = {https://theasc.com/articles/real-time-ray-tracing-virtual-production}
  % CHECK printed title and pages
}

@inproceedings{hill2023stagecraft,
  author    = {Hill, Stephen and Schulte, Jeroen},
  title     = {Lights, Camera, Interaction! The Real-Time Technology of {ILM StageCraft}},
  booktitle = {Proceedings of the 2023 Digital Production Symposium (DigiPro '23)},
  year      = {2023},
  publisher = {ACM}
  % CHECK title, authors, DOI: not read
}

@misc{epic2024icvfx,
  author       = {{Epic Games}},
  title        = {In-Camera {VFX} Overview},
  howpublished = {Unreal Engine documentation},
  year         = {2024},
  url          = {https://dev.epicgames.com/documentation/unreal-engine/in-camera-vfx-overview-in-unreal-engine}
  % CHECK year of the version you cite
}

@inproceedings{lee2025automated,
  author    = {Lee, Ho Yuen and Luk, Kai Hang},
  title     = {Automated Lighting in Virtual Production using Real-Time Image Processing Technique},
  booktitle = {SIGGRAPH Asia 2025 Technical Communications},
  year      = {2025},
  doi       = {10.1145/3757376.3771412}
}

@inproceedings{legendre2019deeplight,
  author    = {LeGendre, Chloe and Ma, Wan-Chun and Fyffe, Graham and Flynn, John and Charbonnel, Laurent and Busch, Jay and Debevec, Paul},
  title     = {{DeepLight}: Learning Illumination for Unconstrained Mobile Mixed Reality},
  booktitle = {IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)},
  year      = {2019}
  % CHECK pages
}

@inproceedings{somanath2021hdr,
  author    = {Somanath, Gowri and Kurz, Daniel},
  title     = {{HDR} Environment Map Estimation for Real-Time Augmented Reality},
  booktitle = {IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)},
  year      = {2021}
  % CHECK pages
}

@inproceedings{zhao2021xihe,
  author    = {Zhao, Yiqin and Guo, Tian},
  title     = {Xihe: A {3D} Vision-based Lighting Estimation Framework for Mobile Augmented Reality},
  booktitle = {Proceedings of the 19th Annual International Conference on Mobile Systems, Applications, and Services (MobiSys '21)},
  year      = {2021},
  publisher = {ACM}
  % CHECK DOI
}

@article{li2023spatiotemporally,
  author  = {Li, Zhengqin and Yu, Li and Okunev, Mikhail and Chandraker, Manmohan and Dong, Zhao},
  title   = {Spatiotemporally Consistent {HDR} Indoor Lighting Estimation},
  journal = {ACM Transactions on Graphics},
  year    = {2023}
  % CHECK volume, number, article number, DOI
}

@inproceedings{bolduc2026limo,
  author    = {Bolduc, Christophe and Philip, Julien and Ma, Li and He, Mingming and Debevec, Paul and Lalonde, Jean-Fran{\c{c}}ois},
  title     = {Lighting in Motion: Spatiotemporal {HDR} Lighting Estimation},
  booktitle = {IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)},
  year      = {2026},
  note      = {arXiv:2512.13597}
}

@article{rhee2017mr360,
  author  = {Rhee, Taehyun and Petikam, Lohit and Allen, Benjamin and Chalmers, Andrew},
  title   = {{MR360}: Mixed Reality Rendering for 360{\textdegree} Panoramic Videos},
  journal = {IEEE Transactions on Visualization and Computer Graphics},
  volume  = {23},
  number  = {4},
  pages   = {1379--1388},
  year    = {2017},
  doi     = {10.1109/TVCG.2017.2657178}
}

@inproceedings{rhee2018mr360live,
  author    = {Rhee, Taehyun and Chalmers, Andrew and Loh, Ian and Allen, Ben and Petikam, Lohit and Thompson, Stephen and Revill, Tom},
  title     = {Mixed Reality 360 Live: Live Blending of Virtual Objects into 360{\textdegree} Streamed Video},
  booktitle = {ACM SIGGRAPH 2018 Real-Time Live!},
  year      = {2018}
  % CHECK DOI
}

@article{kronander2015photorealistic,
  author  = {Kronander, Joel and Banterle, Francesco and Gardner, Andrew and Miandji, Ehsan and Unger, Jonas},
  title   = {Photorealistic Rendering of Mixed Reality Scenes},
  journal = {Computer Graphics Forum},
  volume  = {34},
  number  = {2},
  pages   = {643--665},
  year    = {2015},
  doi     = {10.1111/cgf.12591}
}

@inproceedings{saito2024relightable,
  author    = {Saito, Shunsuke and Schwartz, Gabriel and Simon, Tomas and Li, Junxuan and Nam, Giljoo},
  title     = {Relightable {Gaussian} Codec Avatars},
  booktitle = {IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)},
  year      = {2024}
  % CHECK pages
}

@inproceedings{cheng2023environment,
  author    = {Cheng, Haojie and Xu, Chunxiao and Chen, Xujing and Chen, Zhenxin and Wang, Jiajun and Zhao, Lingxiao},
  title     = {Realistic Volume Rendering with Environment-Synced Illumination in Mixed Reality},
  booktitle = {2023 IEEE International Symposium on Mixed and Augmented Reality Adjunct (ISMAR-Adjunct)},
  pages     = {423--428},
  year      = {2023},
  doi       = {10.1109/ISMAR-Adjunct60411.2023.00090}
}

@article{wu2024panoramic,
  author  = {Wu, Jian and Wang, Lili},
  title   = {Panoramic Ray Tracing for Interactive Mixed Reality Rendering Based on 360{\textdegree} {RGBD} Video},
  journal = {IEEE Computer Graphics and Applications},
  volume  = {44},
  number  = {1},
  pages   = {62--75},
  year    = {2024},
  doi     = {10.1109/MCG.2023.3327383}
}

@inproceedings{taibo2024immersive,
  author    = {Taibo, Javier and Iglesias-Guitian, Jose A.},
  title     = {Immersive {3D} Medical Visualization in Virtual Reality using Stereoscopic Volumetric Path Tracing},
  booktitle = {2024 IEEE Conference Virtual Reality and 3D User Interfaces (VR)},
  pages     = {1044--1053},
  year      = {2024},
  doi       = {10.1109/VR58804.2024.00123}
}

@inproceedings{walton2018dynamic,
  author    = {Walton, David R. and Steed, Anthony},
  title     = {Dynamic {HDR} Environment Capture for Mixed Reality},
  booktitle = {Proceedings of the 24th ACM Symposium on Virtual Reality Software and Technology (VRST '18)},
  year      = {2018},
  doi       = {10.1145/3281505.3281531}
}

@article{shen2025stglight,
  author  = {Shen, Shiyuan and Bao, Zhongyun and Ding, Hong and Xu, Wenju and Lai, Tenghui and Xiao, Chunxia},
  title   = {{STGlight}: Online Indoor Lighting Estimation via Spatio-Temporal {Gaussian} Fusion},
  journal = {ACM Transactions on Graphics},
  volume  = {44},
  number  = {6},
  year    = {2025},
  doi     = {10.1145/3763350}
}

@article{alhakamy2020realtime,
  author  = {Alhakamy, A'aeshah and Tuceryan, Mihran},
  title   = {Real-time Illumination and Visual Coherence for Photorealistic Augmented/Mixed Reality},
  journal = {ACM Computing Surveys},
  volume  = {53},
  number  = {3},
  pages   = {1--34},
  year    = {2020},
  doi     = {10.1145/3386496}
}

@inproceedings{tarko2019realtime,
  author    = {Tarko, Joanna and Tompkin, James and Richardt, Christian},
  title     = {Real-time Virtual Object Insertion for Moving 360{\textdegree} Videos},
  booktitle = {Proceedings of the 17th ACM SIGGRAPH International Conference on Virtual-Reality Continuum and its Applications in Industry (VRCAI '19)},
  year      = {2019},
  doi       = {10.1145/3359997.3365708}
}

@inproceedings{chen2026lightopt,
  author    = {Chen, Tuo and Cao, Luyan and Wu, Kui and Hu, Shimin},
  title     = {{LightOpt}: Lights Optimization for Real-time Rendering},
  booktitle = {ACM SIGGRAPH 2026 Conference Papers},
  year      = {2026},
  doi       = {10.1145/3799902.3811072}
}

@article{coomans2026irradiance,
  author  = {Coomans, Arno and Nazzaro, Giacomo and Dominici, Edoardo A. and D{\"o}ring, Christian and Verhoeven, Floor and Vardis, Konstantinos and Steinberger, Markus},
  title   = {Real-time Rendering with a Neural Irradiance Volume},
  journal = {Computer Graphics Forum},
  year    = {2026},
  pages   = {e70400},
  doi     = {10.1111/cgf.70400}
  % CHECK volume and issue
}

@misc{coomans2026emitters,
  author       = {Coomans, Arno and Verhoeven, Floor and Dominici, Edoardo A. and Steinberger, Markus},
  title        = {Real-time Rendering of Pre-integrated Neural Emitters},
  howpublished = {arXiv:2610.06762},
  year         = {2026}
}

@inproceedings{freire2024dynamic,
  author    = {Freire, Pedro da Silva and Pereira, Jo{\~a}o Madeiras},
  title     = {Dynamic Many-Light Importance Sampling for Real-Time Ray Tracing},
  booktitle = {Computer Science Research Notes (WSCG 2024)},
  year      = {2024},
  doi       = {10.24132/CSRN.3401.45}
}

@inproceedings{bengtsson2022ibl,
  author    = {Bengtsson, Marcus and Kang, Timothy S.},
  title     = {Image Based Lighting - Current Capabilities and Limitations},
  booktitle = {SMPTE 2022 Media Technology Summit},
  pages     = {1--15},
  year      = {2022},
  doi       = {10.5594/M001992}
}

@article{kadner2023stages,
  author  = {Kadner, Noah},
  title   = {The Virtual World: Stages of Color on {The Book of Boba Fett}},
  journal = {American Cinematographer},
  year    = {2023},
  month   = jan,
  url     = {https://theasc.com/article/stages-of-color-book-of-boba-fett/}
  % CHECK printed issue and pages; quotes obtained through a summarizing tool
}

@misc{kadner2021fieldguide,
  author       = {Kadner, Noah},
  title        = {The Virtual Production Field Guide, Volume 2},
  howpublished = {Epic Games},
  year         = {2021},
  url          = {https://cdn2.unrealengine.com/Virtual+Production+Field+Guide+Volume+2+v1.0-5b06b62cbc5f.pdf}
}

@book{zwerman2023ves,
  editor    = {Zwerman, Susan and Okun, Jeffrey A.},
  title     = {The {VES} Handbook of Virtual Production},
  publisher = {Focal Press},
  year      = {2023},
  doi       = {10.4324/9781003366515}
  % CHECK book DOI (chapter DOIs are 10.4324/9781003366515-8, -23, -24); a third editor, Susan Thurmond O'Neal, appears in the chapter records
}

@incollection{dinur2023realtime,
  author    = {Dinur, Eran},
  title     = {Real-time Rendering and Virtual Production},
  booktitle = {The Filmmaker's Guide to Visual Effects},
  publisher = {Routledge},
  pages     = {177--187},
  year      = {2023},
  doi       = {10.4324/9781003289371-14}
}

@misc{seymour2013gravity,
  author       = {Seymour, Mike},
  title        = {Gravity: vfx that's anything but down to earth},
  howpublished = {fxguide},
  year         = {2013},
  month        = oct,
  url          = {https://www.fxguide.com/fxfeatured/gravity/}
}

@article{bunish2017rogueone,
  author  = {Bunish, Christine},
  title   = {Cover Story: {Rogue One: A Star Wars Story}},
  journal = {Post Magazine},
  year    = {2017},
  month   = jan,
  url     = {https://www.postmagazine.com/Publications/Post-Magazine/2017/January-1-2017/Cover-Story-i-Rogue-One-A-Star-Wars-Story-i-.aspx}
}

@misc{failes2020mandalorian,
  author       = {Failes, Ian},
  title        = {{The Mandalorian} and the Future of Filmmaking},
  howpublished = {VFX Voice},
  year         = {2020},
  month        = apr,
  url          = {https://vfxvoice.com/the-mandalorian-and-the-future-of-filmmaking/}
}

@misc{failes2022hotd,
  author       = {Failes, Ian},
  title        = {Motion bases and making mayhem, in the volume},
  howpublished = {befores \& afters},
  year         = {2022},
  month        = dec,
  url          = {https://beforesandafters.com/2022/12/01/motion-bases-and-making-mayhem-in-the-volume/}
}

@misc{failes2024hotd,
  author       = {Failes, Ian},
  title        = {Motion bases, mo-co cameras and monofilament wires},
  howpublished = {befores \& afters},
  year         = {2024},
  month        = sep,
  url          = {https://beforesandafters.com/2024/09/10/motion-bases-mo-co-cameras-and-monofilament-wires/}
}

@article{nash2025integration,
  author  = {Nash, Chris and Butt, Nathan and Loriedo, Andrea and Spooner, Robin and Ha, Taegyun and Coulam-Jones, Philip and Bentley, James and Smolic, Aljosa},
  title   = {Integration of Depth and Volumetric Capture Workflows for {2.5D} Virtual Production},
  journal = {SMPTE Motion Imaging Journal},
  volume  = {134},
  number  = {6},
  pages   = {50--58},
  year    = {2025},
  doi     = {10.5594/JMI.2025/FOOS6445}
}

@inproceedings{hendry2023cinedesk,
  author    = {Hendry, Manuel Flurin and Kottmann, Norbert and Huber, Valentin Karl and Schaerer, Michael and Iseli, Christian},
  title     = {Simulate This! Virtual Production and Cinematic Education with {cineDESK}},
  booktitle = {AVANCA | CINEMA 2023},
  year      = {2023},
  doi       = {10.37390/avancacinema.2023.a541}
}

@inproceedings{deese2022unreal,
  author    = {Deese, Frank},
  title     = {Unreal Savings: Budget Previs/Techvis for Student Films},
  booktitle = {SMPTE 2022 Media Technology Summit},
  pages     = {1--7},
  year      = {2022},
  doi       = {10.5594/M001989}
}

@inproceedings{sengupta2021lightstage,
  author    = {Sengupta, Soumyadip and Curless, Brian and Kemelmacher-Shlizerman, Ira and Seitz, Steven M.},
  title     = {A Light Stage on Every Desk},
  booktitle = {IEEE/CVF International Conference on Computer Vision (ICCV)},
  year      = {2021}
  % CHECK pages and DOI
}

@article{yeh2022virtuallightstage,
  author  = {Yeh, Yu-Ying and Nagano, Koki and Khamis, Sameh and Kautz, Jan and Liu, Ming-Yu and Wang, Ting-Chun},
  title   = {Learning to Relight Portrait Images via a Virtual Light Stage and Synthetic-to-Real Adaptation},
  journal = {ACM Transactions on Graphics},
  volume  = {41},
  number  = {6},
  year    = {2022},
  doi     = {10.1145/3550454.3555442}
}

@inproceedings{clausen2024fitting,
  author    = {Clausen, Pascal and Ma, Li and He, Mingming and Ta{\c{s}}el, Ahmet Levent and Pilarski, Oliver and Debevec, Paul},
  title     = {Fitting Spherical {Gaussians} to Dynamic {HDRI} Sequences},
  booktitle = {SIGGRAPH Asia 2024 Posters},
  year      = {2024},
  doi       = {10.1145/3681756.3698208}
}

@inproceedings{yu2025multispectral,
  author    = {Yu, Xueming and George, David and Millward, John and Debevec, Paul},
  title     = {Real-Time Multispectral Lighting Reproduction},
  booktitle = {ACM SIGGRAPH 2025 Posters},
  year      = {2025},
  doi       = {10.1145/3721250.3743035}
}
```
