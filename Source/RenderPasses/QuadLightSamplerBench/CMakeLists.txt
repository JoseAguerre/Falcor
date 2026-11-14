add_plugin(QuadLightSamplerBench)

target_sources(QuadLightSamplerBench PRIVATE
    QuadLightSamplerBench.cpp
    QuadLightSamplerBench.h
    SamplerBench.cs.slang
    CacheChase.cs.slang
    GpuBuild.cs.slang
)

target_copy_shaders(QuadLightSamplerBench RenderPasses/QuadLightSamplerBench)

target_source_group(QuadLightSamplerBench "RenderPasses")
