#version 330
#extension GL_ARB_separate_shader_objects : require

#include <minecraft:globals.glsl>

uniform sampler2D MainSampler;
uniform sampler2D PreviousSampler;

layout(location = 0) in vec2 texCoord;
layout(location = 0) out vec4 fragColor;

layout(std140) uniform SamplerInfo {
    vec2 OutSize;
    vec2 MainSize;
    vec2 PreviousSize;
};

float readDigit(int pixel) {
    if (pixel >= int(MainSize.x)) {
        return -1.0;
    }
    vec4 value = round(texelFetch(MainSampler, ivec2(pixel, 0), 0) * 255.0);
    return all(equal(value.gba, vec3(57.0, 143.0, 211.0))) ? value.r : -1.0;
}

float readAxis(int first) {
    float result = 0.0;
    for (int digit = 0; digit < 4; ++digit) {
        float value = readDigit(first + digit);
        if (value < 0.0 || value > 15.0) {
            return 32767.0;
        }
        result += value * pow(16.0, float(digit));
    }
    return result;
}

void main() {
    // GameTime is a smoothly advancing fraction of a 24000-tick day.
    float clock = fract(GameTime);
    if (texCoord.x >= 0.5) {
        float heading = readDigit(8);
        float previousHeading = round(texelFetch(PreviousSampler, ivec2(1, 0), 0).a * 255.0) - 128.0;
        if (heading < 0.0 || heading > 63.0) {
            heading = previousHeading >= 0.0 && previousHeading <= 63.0 ? previousHeading : 0.0;
        }
        float encoded = floor(clock * 16777215.0);
        fragColor = vec4(floor(encoded / 65536.0), mod(floor(encoded / 256.0), 256.0), mod(encoded, 256.0), 128.0 + heading) / 255.0;
        return;
    }
    vec2 target = vec2(readAxis(0), readAxis(4));
    vec4 previous = round(texelFetch(PreviousSampler, ivec2(0), 0) * 255.0);
    vec4 time = round(texelFetch(PreviousSampler, ivec2(1, 0), 0) * 255.0);
    vec2 current = vec2(previous.r * 256.0 + previous.g, previous.b * 256.0 + previous.a);
    float previousClock = dot(time.rgb, vec3(65536.0, 256.0, 1.0)) / 16777215.0;
    float elapsed = fract(clock - previousClock) * 1200.0;
    bool valid = time.a >= 128.0 && time.a <= 191.0 && elapsed < 0.25;
    float weight = 1.0 - exp(-elapsed / 0.035);
    vec2 difference = abs(target - current);
    weight = max(weight, 1.0 / max(1.0, max(difference.x, difference.y)));
    vec2 result = round(valid ? mix(current, target, weight) : target);
    fragColor = vec4(floor(result.x / 256.0), mod(result.x, 256.0), floor(result.y / 256.0), mod(result.y, 256.0)) / 255.0;
}
