#version 330
#extension GL_ARB_separate_shader_objects : require

layout(std140) uniform SamplerInfo {
    vec2 OutSize;
};

layout(std140) uniform PanSignal {
    vec2 Signal;
};

layout(location = 0) out vec2 pixelCoord;

void main() {
    pixelCoord = vec2((gl_VertexIndex << 1) & 2, gl_VertexIndex & 2);
    vec2 pixel = vec2(Signal.x, 0.0) + pixelCoord;
    gl_Position = vec4(pixel * 2.0 / OutSize - 1.0, 0.0, 1.0);
}
