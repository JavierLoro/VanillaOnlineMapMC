#version 330
#extension GL_ARB_separate_shader_objects : require
layout(std140) uniform SamplerInfo { vec2 OutSize; vec2 InSize; };
layout(location = 0) out vec2 texCoord;
void main() {
    texCoord = vec2((gl_VertexIndex << 1) & 2, gl_VertexIndex & 2);
    vec2 pixel = vec2(0, 2) + texCoord * vec2(16, 17);
    gl_Position = vec4(pixel * 2.0 / OutSize - 1.0, 0, 1);
}
