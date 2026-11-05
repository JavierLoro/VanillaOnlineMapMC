#version 330
#extension GL_ARB_separate_shader_objects : require

layout(std140) uniform PanSignal {
    vec2 Signal;
};

layout(location = 0) in vec2 pixelCoord;
layout(location = 0) out vec4 fragColor;

void main() {
    if (any(greaterThanEqual(pixelCoord, vec2(1.0)))) {
        discard;
    }
    // Reserve the other three channels to distinguish the signal from the scene.
    fragColor = vec4(Signal.y, 57.0, 143.0, 211.0) / 255.0;
}
