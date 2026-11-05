#version 330
#extension GL_ARB_separate_shader_objects : require

#include <minecraft:globals.glsl>

uniform sampler2D MainSampler;
uniform sampler2D MapSampler;

layout(location = 0) in vec2 texCoord;
layout(location = 0) out vec4 fragColor;

layout(std140) uniform SamplerInfo {
    vec2 OutSize;
    vec2 MainSize;
    vec2 MapSize;
};

layout(std140) uniform MapConfig {
    ivec3 MapOrigin;
    float ViewHeight;
    vec2 MapWorldSize;
    float PanStep;
};

float readPan(int axis) {
    if (axis >= int(MainSize.x)) {
        return 0.0;
    }
    vec4 pixel = round(texelFetch(MainSampler, ivec2(axis, 0), 0) * 255.0);
    if (all(equal(pixel.gba, vec3(57.0, 143.0, 211.0)))) {
        return pixel.r - 127.0;
    }
    return 0.0;
}

void main() {
    // Keep north at the top and use the same number of blocks per pixel on both axes.
    vec2 screenOffset = vec2(texCoord.x - 0.5, 0.5 - texCoord.y);
    vec2 viewSize = vec2(OutSize.x / OutSize.y, 1.0) * ViewHeight;
    vec2 camera = vec2(CameraBlockPos.xz - MapOrigin.xz) - CameraOffset.xz;
    vec2 pan = vec2(readPan(0), readPan(1)) * PanStep;
    vec2 playerOffset = pan + screenOffset * viewSize;
    vec2 uv = (camera + playerOffset) / MapWorldSize;
    vec3 background = vec3(29.0, 39.0, 48.0) / 255.0;
    vec3 color = background;
    if (all(greaterThanEqual(uv, vec2(0.0))) && all(lessThan(uv, vec2(1.0)))) {
        vec4 mapPixel = texture(MapSampler, uv);
        color = mix(background, mapPixel.rgb, mapPixel.a);
    }
    if (any(notEqual(pan, vec2(0.0)))) {
        float distanceToPlayer = length(playerOffset * OutSize.y / ViewHeight);
        if (distanceToPlayer < 6.0) {
            color = distanceToPlayer < 4.0 ? vec3(0.35, 0.85, 1.0) : background;
        }
    }
    fragColor = vec4(color, 1.0);
}
