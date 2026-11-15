# Why real-time sampling of dynamic emissive textures matters: references and draft text

Prepared 14 Nov 2026 for the TOG-26-0166 revision. Nothing in the paper was changed; this is the only file created.

## How to read this

- Every quotation below was copied from the source text itself (PDF, slides or official documentation), except where a line is marked **[not read in full]**. For those I saw only an abstract, a catalogue record or a search summary, so check the wording before quoting.
- Section 1 is the draft text for the paper. Section 2 ranks the cases. Section 3 gives the evidence per reference. Section 4 lists what I would leave out. Section 5 lists weak points a reviewer could raise. Section 6 is BibTeX.
- Three references from the earlier quick list are already in `sample-base.bib` and are reused here with their existing keys: `bitterli2020spatiotemporal`, `binder2019radix`, `lu2013realtime`.

---

## 1. Draft paragraphs (LaTeX-ready)

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

\paragraph{Virtual production.}
On an LED stage the wall is at once the in-camera background and the light source of
the scene: the stage is driven as an image-based lighting instrument
\cite{debevec2002lighting,hamon2014gravity,debevec2022dilation}, and the pixels outside
the camera frustum exist to illuminate the subjects \cite{legendre2022jointly}. The
content of the wall is rendered in real time, with ray tracing in production renderers
\cite{hill2023stagecraft} and, more recently, with full path tracing at 24 frames per
second and above \cite{kadner2024raytracing}, and it is edited while the camera rolls.
Recent work treats the wall as what it is for a renderer, a near-field,
high-resolution textured emitter whose image is known at every frame
\cite{azzarelli2026relightable}, and uses LED stages to reproduce per-frame HDR
environment maps at video rate \cite{zhang2026pixelcube}. Any synthetic element that
must match the stage, such as a digital character, a set extension or a preview of the
shot rendered before the stage is built, has to be lit by that same video, and its
sampling structure has to follow the wall frame by frame.

\paragraph{Mixed reality and telepresence.}
In augmented and mixed reality the illumination is not authored at all: it is captured
or estimated while the application runs. HDR environment maps are inferred from the
camera feed at interactive rates on mobile devices
\cite{legendre2019deeplight,somanath2021hdr,zhao2021xihe}, estimated consistently over
video \cite{li2023spatiotemporally,bolduc2026limo}, or taken directly from a live
$360^\circ$ stream with changing real-world lights \cite{rhee2017mr360,rhee2018mr360live}.
For such high-frequency illumination, importance sampling of the environment map is
essential for efficient rendering \cite{kronander2015photorealistic}, yet current
real-time systems avoid it: they prefilter the map or reduce it to a few dominant
lights, because, as Saito et al.~\cite{saito2024relightable} state for photorealistic
avatars on a VR headset, existing relighting models are ``often too slow to render in
real-time with high-resolution continuous environments''. A sampling structure that can
be rebuilt at the rate of the display, and that is small enough to keep one per light,
is a precondition for moving these applications from prefiltered shading to path
tracing with correct shadows and interreflections.
```

Notes on these paragraphs:

- The last sentence of the virtual-production paragraph and the last sentence of the mixed-reality paragraph are **our argument**, not something a cited source states. I found no peer-reviewed source saying that a previs or on-set path tracer importance-samples the wall, and none saying that XR systems avoid Monte Carlo *because of* the per-frame build cost. The text is worded so that it does not attribute those claims to anyone.
- "prefilter the map or reduce it to a few dominant lights" is supported by Saito et al. (prefiltered mip lookup) and by MR360 (salient light detection). The MR360 detail comes from a talk abstract, so soften it to "prefilter the map" if you cannot check the paper.
- XR headsets run at 72 to 120 Hz; none of the cited papers gives that number in the passages I read, so the paragraph says "the rate of the display" instead of a figure.

---

## 2. The six strongest cases, ranked

| # | Case | Lead references | Why it is strong |
|---|------|-----------------|------------------|
| 1 | Sampling-structure build cost blocks dynamic textured lights in real-time path tracing | Wyman and Panteleev 2021; Bitterli et al. 2020; RTXDI integration guide | States our exact problem, with a number (alias build over 200 ms) and our exact use case (live 360° probes). Published at HPG by the ReSTIR authors. |
| 2 | Initial light-sample quality limits ReSTIR | Zeng et al., SIGGRAPH Asia 2025; Kozlowski, SIGGRAPH 2023 course; Lin et al. 2026 | Answers "resampling will fix a poor sampler". Recent, SIGGRAPH venues. |
| 3 | Engines and artists are moving to emissive and textured lights | Wright et al. 2022 (Lumen); Narkowicz and Costa 2025 (MegaLights); NVIDIA 2026 whitepaper | Three shipping-engine sources across four years, each naming noise or cost from emissive or textured lights. |
| 4 | LED walls are video-driven light sources rendered live | Debevec et al. 2002 (TOG); LeGendre et al. 2022; Debevec and LeGendre 2022; Zhang et al. 2026 (TOG); Kadner 2024; Hill and Schulte 2023 | Establishes the wall as an image-based light whose content changes per frame, with two TOG papers. Does not mention importance sampling. |
| 5 | XR lighting is estimated or captured per frame | LeGendre et al. 2019; Somanath and Kurz 2021; Li et al. 2023 (TOG); Bolduc et al. 2026; Rhee et al. 2017, 2018 | A whole research line whose output is a new HDR environment map every frame or every few frames. |
| 6 | Real -time relighting under continuous environments is still too slow | Saito et al., CVPR 2024; Kronander et al. 2015 (Eurographics STAR) | Saito gives the "too slow" statement; the STAR gives the "importance sampling is essential" statement. |

Cases 1 to 3 mention sampling, noise or build cost directly. Cases 4 to 6 establish that the dynamic light exists and is needed in real time; the link to sampling is ours.

---

## 3. Evidence per reference

### 3.1 Games and real-time path tracing

**Wyman and Panteleev, "Rearchitecting Spatiotemporal Resampling for Production", HPG 2021** (`wyman2021rearchitecting`)
- "Alias tables allow cheap O(1) sampling, which is vital with 64 million samples a frame. But optimal table builds cost O(N) [Vos91] and do not parallelize trivially on GPUs. In moderate complexity scenes CPU builders take under 0.5 ms, but build costs for large environment maps exceed 200 ms."
- "For dynamic light probes, we can substitute alternative approaches. Binder and Keller [BK19] propose one option, quickly building a radix forest to sample via the cutpoint method".
- "Building our hierarchy costs around 60 µs for a 2048×1024 light probe. Lookups are O(log N), but occur outside the inner loop, thanks to presampling. This allows truly dynamic textured emissives, e.g., light probes streamed live from a 360 camera."
- The teaser scene has "2001 analytic primitive lights and 453 emissive" lights in a "dynamic night city scene, rendered in a driving simulator in 31 ms".
- Read the caution in section 5 before using this one.

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

### 3.2 Virtual production

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

### 3.3 Mixed reality, AR and telepresence

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

---

## 4. Candidates I would leave out

| Candidate | Reason |
|-----------|--------|
| James et al., "Colour-Managed LED Walls", SIGGRAPH 2021 Talks | About colour calibration. Says nothing on lighting or rendering cost. LeGendre 2022 covers the same ground and does mention lighting. |
| Li et al., "URAvatar", SIGGRAPH Asia 2024 | Same point as Saito 2024, weaker wording ("without expensive ray tracing"). One avatar paper is enough. |
| Sengupta et al., "A Light Stage on Every Desk", ICCV 2021 | A monitor showing video as a light source for face relighting. A nice illustration of a video-textured light, but it is a capture method, not rendering. |
| Zhao et al., "LitAR", IMWUT 2022 | Real-time environment maps for AR reflections. Duplicates Xihe and EnvMapNet. |
| Majercik et al., "Scaling Probe-Based Real-Time Dynamic GI for Production", JCGT 2021 | Shows a scene lit mostly by emissive monitor screens, but handles them through probes, with no sampling discussion. |
| Ray Tracing Gems II, ch. 39 (Morrical and Zellmann) | Already cited in the paper. |
| Wu and Wang, "Panoramic Ray Tracing for Interactive MR Rendering Based on 360° RGBD Video", IEEE CG&A 2024 | Relevant (ray-traced lighting from 360° video in real time) but I could not read it. Worth a look if you want a second XR ray-tracing reference. |
| RelightVid, Lux Post Facto, CamLit and other video-diffusion relighting papers | They take per-frame HDR maps as conditioning, not as lights in a renderer. The link to sampling is too indirect. |
| Epic "Speed of Light" demo, SIGGRAPH 2018 | First real-time "animated textured area lights with ray-traced soft shadows". Only blog sources; eight years old. |

---

## 5. Weak points a reviewer could raise

1. **Wyman and Panteleev cut both ways.** The same passage that gives the 200 ms alias-build figure also says their mip hierarchy is built in "around 60 µs for a 2048×1024 light probe". So that paper supports "per-texel alias tables cannot be rebuilt per frame", and does not support "no existing structure can be built per frame". The argument for LeafAlias against a mip hierarchy has to rest on cost per sample (their lookups are O(log N), and they hide them by presampling) and on memory per light, which is where the revision's own measurements point.
2. **Virtual production sources do not mention sampling.** They establish that the wall is a per-frame image-based light and that its content is rendered and edited live. The step to "a renderer must importance-sample it per frame" is ours. I found no peer-reviewed source for path-traced previs or digital twins of LED stages.
3. **XR and avatar systems use prefiltering, not sampling.** They show demand for real-time lighting from dynamic environment maps. A reviewer can answer that prefiltering works for them. The reply is that prefiltering gives no shadows or interreflections, which is the reason the STAR calls importance sampling essential.
4. **Several sources are not peer reviewed**: the two Advances course talks, the ReSTIR course slides, the NVIDIA whitepaper and RTXDI guide, the Epic documentation, the Khronos note and the American Cinematographer article. Course material is normal to cite in TOG; I would keep the whitepaper, documentation and trade press to at most one each, or move them to footnotes.
5. **Items not read in full** are marked in section 3: Hamon 2014, Hill and Schulte 2023, Lee and Luk 2025, Rhee 2017, Debevec 2002 (abstract only), and the quotes from Zhang 2026 and Kadner 2024 that came through a summarizing tool.
6. **Frame rates.** The paper uses 30 fps. The LED-stage sources give 24 fps (camera) and 60 fps (Pixel Cube capture); XR sources give per-estimate times of 9 to 21 ms. None contradicts the 33 ms budget, and the XR case is stricter.

---

## 6. BibTeX

Fields marked `% CHECK` were not confirmed against the publisher record.

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
  author    = {Hamon, Pierre-Loic and Harmer, James and Penn, Stuart and Scapel, Nicolas},
  title     = {Gravity: Motion Control and Face Integration},
  booktitle = {ACM SIGGRAPH 2014 Talks},
  year      = {2014},
  articleno = {35},
  doi       = {10.1145/2614106.2614193}
  % CHECK first names
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
  author    = {Lee and Luk},
  title     = {Automated Lighting in Virtual Production using Real-Time Image Processing Technique},
  booktitle = {SIGGRAPH Asia 2025 Technical Communications},
  year      = {2025},
  doi       = {10.1145/3757376.3771412}
  % CHECK first names: only family names confirmed
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
```

---

## 7. Second pass: bulk screening of about 30,000 papers

### 7.1 What was done

- **Venue sweep, 2015 to 2026**, metadata and abstracts from OpenAlex: all of ACM TOG (3,550 records), IEEE TVCG (5,414), Computer Graphics Forum (3,351), The Visual Computer, Computers & Graphics, IEEE CG&A, SMPTE Motion Imaging Journal, PACM CGIT (I3D and HPG papers), SIGGRAPH conference papers, SIGGRAPH Talks, SIGGRAPH Asia Technical Communications, DigiPro. About 26,700 unique records, 18,600 with an abstract.
- **Fifty keyword searches across all venues** (about 5,000 records) and a second index (Semantic Scholar) for CVPR, ICCV, ECCV, NeurIPS, 3DV, ISMAR, IEEE VR, EGSR, HPG and Eurographics (656 records).
- **Total: 30,127 unique records.** Each was scored on its title and abstract for the combination light source + dynamic content + sampling, noise or real time. I read the top 490 or so titles and the full abstracts of about 30.
- **Full text**: 473 open-access PDFs downloaded and searched sentence by sentence for a light term, a dynamic term and a sampling or cost term together.

Limits, so you can judge coverage:

- The free quota of the index ran out before the sweep finished. ISMAR, IEEE VR, SIGGRAPH Courses and Posters, and SIGGRAPH Asia conference papers from 2017 on are covered only by their 200 most-cited records each, plus whatever the keyword searches caught. A free API key would lift this limit; getting one requires sending an email address to the service, so I did not do it.
- About 30% of the records have no abstract in the index and were screened by title only.
- Full text was reachable for 473 papers only. Most graphics papers are behind publisher walls or have no open-access link in the index.
- Screening by keyword finds papers that say these things in the abstract. A paper that mentions the problem only in its body, and is not open access, is missed.

### 7.2 Outcome in one paragraph

The bulk pass did not change the ranking in section 2. No paper in the 30,000 states the problem more directly than Wyman and Panteleev 2021, and none in virtual production discusses sampling of the wall. Within what was screened, I found no direct successor after 2015 to the already-cited work on sampling dynamic environment maps (Havran 2005, Wan 2005 and 2011, Lu 2013, Kronander 2014) apart from your own 2026 poster; given the coverage limits above, treat that as "none found", not "none exists". It added twelve usable references, strongest in XR, where two papers tie live panoramic lighting to Monte Carlo noise.

### 7.3 New references worth citing

**Mixed reality (the main gain)**

- **Cheng et al., "Realistic Volume Rendering with Environment-Synced Illumination in Mixed Reality", ISMAR-Adjunct 2023** (`cheng2023environment`). Full text read. "The dynamic HDR environment illumination is first estimated consecutively from panoramic images captured using an LDR panorama camera in real-time." A denoiser is then needed "to optimize the DVR results with panoramic HDR illumination." This is a headset application that path-traces under a live panorama and has to fight the noise.
- **Wu and Wang, "Panoramic Ray Tracing for Interactive Mixed Reality Rendering Based on 360° RGBD Video", IEEE CG&A 44(1), 2024** (`wu2024panoramic`). Abstract only: "an irradiance estimation channel is introduced to generate noisy Monte Carlo images", then filtered, to produce "frames for dynamic virtual objects in 360° RGBD videos in real time".
- **Immersive 3D Medical Visualization in VR using Stereoscopic Volumetric Path Tracing, IEEE VR 2024** (`vr2024volumetric`). Full text read: "in VR the interaction never stops, and those techniques are not directly applicable to head-tracked environments as the temporal flicker introduced by MC noise would significantly increase the cybersickness symptoms". Use: in a headset, noise costs more than image quality. **Authors not retrieved; look up DOI 10.1109/VR58804.2024.00123.**
- **Walton and Steed, "Dynamic HDR Environment Capture for Mixed Reality", VRST 2018** (`walton2018dynamic`). Abstract: "capturing and updating a HDR radiance map of the real environment ... in real time", to "render convincing virtual objects whose illumination changes dynamically to reflect the changing real environment around them."
- **Shen et al., "STGlight: Online Indoor Lighting Estimation via Spatio-Temporal Gaussian Fusion", TOG 44(6), 2025** (`shen2025stglight`). Abstract: processes "a stream of LDR RGB-D video frames", "enabling the prediction of HDR environment maps at arbitrary locations for each frame"; earlier methods restrict "applications such as compositing animated models into videos." A second, newer TOG paper for case 5, with "for each frame" in the abstract.
- **Alhakamy and Tuceryan, "Real-time Illumination and Visual Coherence for Photorealistic Augmented/Mixed Reality", ACM Computing Surveys 53(3), 2020** (`alhakamy2020realtime`). A 34-page survey of "dynamic and real-time illumination measurement, estimating, and rendering of augmented reality scenes". Newer than the Kronander STAR; cite both or this one alone if the ten-year limit matters.
- **Tarko, Tompkin and Richardt, "Real-time Virtual Object Insertion for Moving 360° Videos", VRCAI 2019** (`tarko2019realtime`). Abstract: recovers "high dynamic range environment maps which vary spatially along the camera path" and renders in Unity "with dynamic lighting, image-based shadowing".

**Games and real-time rendering**

- **Chen et al., "LightOpt: Lights Optimization for Real-time Rendering", SIGGRAPH 2026 Conference Papers** (`chen2026lightopt`). Abstract: "evaluating many lights per pixel remains a major performance bottleneck in real-time rendering"; the method is extended "to support Time-of-Day lighting."
- **"Real-time Rendering with a Neural Irradiance Volume", Computer Graphics Forum 2026** (`cgf2026neuralirradiance`). Full text read: "real-time rendering requires light sources that can be efficiently sampled to avoid sampling noise." **Authors not retrieved; DOI 10.1111/cgf.70400.**
- **"Real-time Rendering of Pre-integrated Neural Emitters", arXiv 2610.06762, 2026** (`arxiv2026neuralemitters`). Abstract: "Direct illumination from non-trivial emitters with occluding housing, high-polygon emissive meshes, spatially varying emission, or deformable assemblies is a persistent bottleneck in real-time rendering"; "pure sampling-based estimators need high sampling budgets to be noise-free". Preprint. Note that it answers the problem by precomputing the emitter's illumination, which a video texture rules out. **Authors not retrieved.**
- **Freire and Pereira, "Dynamic Many-Light Importance Sampling for Real-Time Ray Tracing", WSCG 2024** (`freire2024dynamic`). Abstract: importance-sampling approaches that "build hierarchical data structures over all light sources" suffer "high maintenance costs for dynamic scenes". Minor venue; built on Falcor. **Author list incomplete in the record.**

**Virtual production**

- **Bengtsson and Kang, "Image Based Lighting - Current Capabilities and Limitations", SMPTE 2022 Media Technology Summit** (`bengtsson2022ibl`). Abstract: image-based lighting "has now evolved into principal photography lighting workflow where the LED video screens are augmented with traditional lighting fixtures, and the video content used to drive the LED video screens also drives the lighting fixtures." This is the clearest statement found that video content is the light on set. Engineering venue, abstract only.

### 7.4 Suggested additions to the draft paragraphs

Mixed-reality paragraph, after the sentence that cites the Kronander survey:

```latex
Systems that do path trace under a live panorama on a head-mounted display report
that the result must be denoised \cite{cheng2023environment,wu2024panoramic}, and
that in a headset Monte Carlo noise is more than a quality problem, since its temporal
flicker aggravates cybersickness \cite{vr2024volumetric}.
```

Mixed-reality paragraph, extend the lighting-estimation citation list with `shen2025stglight` and `walton2018dynamic`, and the survey sentence with `alhakamy2020realtime`.

Virtual-production paragraph, after the first sentence:

```latex
In current practice the same video that drives the wall also drives the lighting
fixtures around it \cite{bengtsson2022ibl}.
```

Games paragraph, optional closing sentence:

```latex
Recent work still describes the evaluation of many lights per pixel as a major
bottleneck of real-time rendering \cite{chen2026lightopt}.
```

### 7.5 Screened and rejected

- **Real-time streaming video relighting** (LiveLight, TOG 2026; LightShift, SIGGRAPH Asia 2026 Real-Time Live; EdgeRelight360, CVPR Workshops 2024; Real-Time 3D-Aware Portrait Video Relighting, CVPR 2024). These show strong 2024 to 2026 interest in relighting video in real time, but they are learned image-to-image methods with no renderer and no light sampling.
- **Relightable avatars** (about twenty papers, 2023 to 2026). All prefilter or use spherical harmonics. Saito 2024 remains the best single citation.
- **Real-time global illumination** (DDGI variants, radiance caches, neural GI; about forty papers). They treat emissive surfaces through probes or caches and do not discuss sampling them.
- **Many-light methods** (stochastic lightcuts, lighting grid hierarchy, Disney's cache points). Relevant to light selection across many lights, not to sampling within one textured light.
- **Lighting estimation from single images** (about sixty papers). Not per-frame; DeepLight, EnvMapNet, Xihe, Li 2023 and STGlight cover the video-rate case.
- **Virtual production in SMPTE and DigiPro** (about thirty records). Colour management, acoustics, pipelines and sustainability. None on rendering cost or sampling apart from the items listed above.

### 7.6 BibTeX for the additions

```bibtex
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

@inproceedings{vr2024volumetric,
  title     = {Immersive {3D} Medical Visualization in Virtual Reality using Stereoscopic Volumetric Path Tracing},
  booktitle = {2024 IEEE Conference on Virtual Reality and 3D User Interfaces (VR)},
  year      = {2024},
  doi       = {10.1109/VR58804.2024.00123}
  % CHECK authors and pages: not retrieved
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

@article{cgf2026neuralirradiance,
  title   = {Real-time Rendering with a Neural Irradiance Volume},
  journal = {Computer Graphics Forum},
  year    = {2026},
  doi     = {10.1111/cgf.70400}
  % CHECK authors, volume, number: not retrieved
}

@misc{arxiv2026neuralemitters,
  title        = {Real-time Rendering of Pre-integrated Neural Emitters},
  howpublished = {arXiv:2610.06762},
  year         = {2026}
  % CHECK authors: not retrieved
}

@inproceedings{freire2024dynamic,
  author    = {Freire, Pedro da Silva and Pereira, Jo{\~a}o Madeiras},
  title     = {Dynamic Many-Light Importance Sampling for Real-Time Ray Tracing},
  booktitle = {Computer Science Research Notes (WSCG 2024)},
  year      = {2024},
  doi       = {10.24132/CSRN.3401.45}
  % CHECK author list: the record shows two blank entries
}

@inproceedings{bengtsson2022ibl,
  author    = {Bengtsson, Marcus and Kang, Timothy S.},
  title     = {Image Based Lighting - Current Capabilities and Limitations},
  booktitle = {SMPTE 2022 Media Technology Summit},
  pages     = {1--15},
  year      = {2022},
  doi       = {10.5594/M001992}
}
```
