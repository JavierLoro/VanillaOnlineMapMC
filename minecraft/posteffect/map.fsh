#version 330
#extension GL_ARB_separate_shader_objects : require

#include <minecraft:globals.glsl>

uniform sampler2D MapSampler;

layout(location = 0) in vec2 texCoord;
layout(location = 0) out vec4 fragColor;

layout(std140) uniform SamplerInfo {
    vec2 OutSize;
    vec2 MapSize;
};

layout(std140) uniform MapConfig {
    ivec3 MapOrigin;
    float ViewHeight;
    vec2 MapWorldSize;
};

void main() {
    // Keep north at the top and use the same number of blocks per pixel on both axes.
    vec2 screenOffset = vec2(texCoord.x - 0.5, 0.5 - texCoord.y);
    vec2 viewSize = vec2(OutSize.x / OutSize.y, 1.0) * ViewHeight;
    vec2 camera = vec2(CameraBlockPos.xz - MapOrigin.xz) - CameraOffset.xz;
    vec2 uv = (camera + screenOffset * viewSize) / MapWorldSize;
    vec3 background = vec3(29.0, 39.0, 48.0) / 255.0;
    if (all(greaterThanEqual(uv, vec2(0.0))) && all(lessThan(uv, vec2(1.0)))) {
        vec4 mapPixel = texture(MapSampler, uv);
        fragColor = vec4(mix(background, mapPixel.rgb, mapPixel.a), 1.0);
    } else {
        fragColor = vec4(background, 1.0);
    }
}
