#version 330
#extension GL_ARB_separate_shader_objects : require

#include <minecraft:globals.glsl>

uniform sampler2D StateSampler;
// TILE_SAMPLERS

layout(location = 0) in vec2 texCoord;
layout(location = 0) out vec4 fragColor;

layout(std140) uniform SamplerInfo {
    vec2 OutSize;
    vec2 StateSize;
    // TILE_SIZES
};

layout(std140) uniform MapConfig {
    ivec3 MapOrigin;
    float ViewHeight;
    vec2 MapWorldSize;
    float PanStep;
    int TileSize;
    int TilesX;
};

vec4 tilePixel(int index, ivec2 pixel) {
    // TILE_FETCH
}

// PLAYER_MARKER

void main() {
    vec2 screenOffset = vec2(texCoord.x - 0.5, 0.5 - texCoord.y);
    vec2 viewSize = vec2(OutSize.x / OutSize.y, 1.0) * ViewHeight;
    vec2 camera = vec2(CameraBlockPos.xz - MapOrigin.xz) - CameraOffset.xz;
    vec4 state = round(texelFetch(StateSampler, ivec2(0), 0) * 255.0);
    vec2 pan = (vec2(state.r * 256.0 + state.g, state.b * 256.0 + state.a) - 32767.0) * PanStep;
    vec2 anchor = clamp(camera, vec2(0.0), MapWorldSize);
    vec2 center = clamp(anchor + pan, vec2(0.0), MapWorldSize);
    vec2 playerOffset = center - camera + screenOffset * viewSize;
    vec2 position = camera + playerOffset;
    vec3 background = vec3(29.0, 39.0, 48.0) / 255.0;
    vec3 color = background;
    if (all(greaterThanEqual(position, vec2(0.0))) && all(lessThan(position, MapWorldSize))) {
        ivec2 block = ivec2(floor(position));
        ivec2 cell = block / TileSize;
        int index = cell.y * TilesX + cell.x;
        vec4 pixel = tilePixel(index, block - cell * TileSize);
        color = mix(background, pixel.rgb, pixel.a);
    }
    color = playerMarker(color, playerOffset, OutSize.y / ViewHeight);
    fragColor = vec4(color, 1.0);
}
