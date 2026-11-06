// Compile/run with LWJGL 3.3.3. Arguments: shader source directory and generated validation directory.
import java.nio.*;
import java.nio.file.*;
import org.lwjgl.glfw.*;
import org.lwjgl.opengl.*;
import static org.lwjgl.glfw.GLFW.*;
import static org.lwjgl.opengl.GL33C.*;

public class CheckLiveProbe {
    static ByteBuffer bytes(int size) { return ByteBuffer.allocateDirect(size).order(ByteOrder.nativeOrder()); }
    static int shader(int type,String source) {
        int id=glCreateShader(type);glShaderSource(id,source);glCompileShader(id);
        if(glGetShaderi(id,GL_COMPILE_STATUS)==0)throw new IllegalStateException(glGetShaderInfoLog(id));return id;
    }
    static void block(int program,String name,int binding,ByteBuffer buffer) {
        int index=glGetUniformBlockIndex(program,name);
        if(glGetActiveUniformBlocki(program,index,GL_UNIFORM_BLOCK_DATA_SIZE)!=buffer.capacity())throw new IllegalStateException(name+" layout");
        int id=glGenBuffers();glBindBuffer(GL_UNIFORM_BUFFER,id);glBufferData(GL_UNIFORM_BUFFER,buffer,GL_STATIC_DRAW);
        glBindBufferBase(GL_UNIFORM_BUFFER,binding,id);glUniformBlockBinding(program,index,binding);
    }
    static int texture(int unit,int width,int height,int... rgba) {
        int id=glGenTextures();glActiveTexture(GL_TEXTURE0+unit);glBindTexture(GL_TEXTURE_2D,id);
        glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_NEAREST);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_NEAREST);
        ByteBuffer p=bytes(width*height*4);for(int v:rgba)p.put((byte)v);p.flip();
        glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA8,width,height,0,GL_RGBA,GL_UNSIGNED_BYTE,p);return id;
    }
    static int program(String vertex, String fragment) {
        int p=glCreateProgram();glAttachShader(p,shader(GL_VERTEX_SHADER,vertex));glAttachShader(p,shader(GL_FRAGMENT_SHADER,fragment));glLinkProgram(p);
        if(glGetProgrami(p,GL_LINK_STATUS)==0)throw new IllegalStateException(glGetProgramInfoLog(p));return p;
    }
    static int framebuffer(int texture) {
        int f=glGenFramebuffers();glBindFramebuffer(GL_FRAMEBUFFER,f);glFramebufferTexture2D(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,texture,0);
        if(glCheckFramebufferStatus(GL_FRAMEBUFFER)!=GL_FRAMEBUFFER_COMPLETE)throw new IllegalStateException("FBO");return f;
    }
    static int[] read(int width,int height) {
        ByteBuffer b=bytes(width*height*4);glReadPixels(0,0,width,height,GL_RGBA,GL_UNSIGNED_BYTE,b);
        int[] result=new int[width*height*4];for(int i=0;i<result.length;i++)result[i]=b.get(i)&255;return result;
    }
    static int[] packet(int group,int revision) {
        int[] data=new int[20];data[0]=127;data[1]=254;data[2]=127;data[3]=255;data[4]=group;data[17]=revision;
        for(int i=0;i<4;i++){data[5+i*3]=group*4+i;data[6+i*3]=group;data[7+i*3]=255-group*4-i;}
        int a=0,b=0;for(int i=0;i<18;i++){a=(a+data[i])%255;b=(b+a)%255;}data[18]=a;data[19]=b;return data;
    }
    static void expected(int[] cache,int[] data) {
        boolean same=cache[(16*16+1)*4]==data[17] && cache[(16*16+2)*4]==83;
        if(!same)java.util.Arrays.fill(cache,0);
        for(int i=0;i<4;i++){int target=(data[4]*4+i)*4;for(int c=0;c<3;c++)cache[target+c]=data[5+i*3+c];cache[target+3]=255;}
        for(int i=0;i<4;i++)cache[16*16*4+i]=data[i];
        int[] meta={data[17],76,86,255,83,84,49,255};System.arraycopy(meta,0,cache,(16*16+1)*4,8);
    }
    static void equal(int[] actual,int[] expected,String context) {
        for(int i=0;i<actual.length;i++)if(actual[i]!=expected[i])throw new IllegalStateException(context+" byte "+i+": "+actual[i]+" != "+expected[i]);
    }
    public static void main(String[] args)throws Exception {
        GLFWErrorCallback.createPrint(System.err).set();if(!glfwInit())throw new IllegalStateException("GLFW");
        glfwWindowHint(GLFW_VISIBLE,GLFW_FALSE);glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR,3);glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR,3);glfwWindowHint(GLFW_OPENGL_PROFILE,GLFW_OPENGL_CORE_PROFILE);
        long window=glfwCreateWindow(64,64,"Live probe validation",0,0);glfwMakeContextCurrent(window);GL.createCapabilities();
        Path root=Path.of(args[0]),helper=Path.of(args[1]);
        String vertex=Files.readString(helper.resolve("screenquad.vsh")).replace("gl_VertexIndex","gl_VertexID");
        int cacheProgram=program(vertex,Files.readString(root.resolve("live_cache.fsh")));
        int stampProgram=program(Files.readString(root.resolve("live_stamp.vsh")).replace("gl_VertexIndex","gl_VertexID"),Files.readString(root.resolve("live_stamp.fsh")));
        int overlayProgram=program(vertex,"#version 330\n#extension GL_ARB_separate_shader_objects : require\nuniform sampler2D LiveSampler;\nconst vec2 LiveSize=vec2(64);\nlayout(location=0) in vec2 texCoord;\nlayout(location=0) out vec4 fragColor;\n"+Files.readString(root.resolve("live_overlay.glsl"))+"\nvoid main(){fragColor=vec4(liveOverlay(vec3(10,20,30)/255.0,vec2(-32,-16)+floor(texCoord*16),texCoord,vec2(64)),1);}");
        // Compile both complete generated map shaders with official 26.3 includes.
        program(vertex,Files.readString(helper.resolve("live-world-14.fsh")));
        program(vertex,Files.readString(helper.resolve("live-map.fsh")));
        glBindVertexArray(glGenVertexArrays());glDisable(GL_DITHER);
        int output=texture(2,16,17,new int[16*17*4]),fbo=framebuffer(output);
        int screen=texture(3,64,64,new int[64*64*4]),screenFbo=framebuffer(screen);
        int[] retained=new int[16*17*4],reference=retained.clone();
        ByteBuffer info=bytes(32);info.putFloat(0,16);info.putFloat(4,17);info.putFloat(8,64);info.putFloat(12,64);info.putFloat(16,16);info.putFloat(20,17);
        int checked=0;
        for(int step=0;step<130;step++) {
            int group=step%64,revision=step<128?7:8;
            int[] data=packet(group,revision),main=new int[64*64*4];
            boolean corrupt=step<64 && group%7==0;
            // First bank retains the prior cache without any signal in the fresh scene.
            glUseProgram(cacheProgram);glBindFramebuffer(GL_FRAMEBUFFER,fbo);glViewport(0,0,16,17);
            block(cacheProgram,"SamplerInfo",0,info);texture(0,64,64,main);texture(1,16,17,retained);
            glUniform1i(glGetUniformLocation(cacheProgram,"MainSampler"),0);glUniform1i(glGetUniformLocation(cacheProgram,"PreviousSampler"),1);
            glDrawArrays(GL_TRIANGLES,0,3);equal(read(16,17),retained,"missing packet");
            // Verify the real stamp pass preserves every scene pixel outside its rectangle.
            glUseProgram(stampProgram);glBindFramebuffer(GL_FRAMEBUFFER,screenFbo);glViewport(0,0,64,64);
            glClearColor(0,0,0,0);glClear(GL_COLOR_BUFFER_BIT);ByteBuffer stampInfo=bytes(16);stampInfo.putFloat(0,64);stampInfo.putFloat(4,64);stampInfo.putFloat(8,16);stampInfo.putFloat(12,17);
            block(stampProgram,"SamplerInfo",0,stampInfo);glActiveTexture(GL_TEXTURE0);glBindTexture(GL_TEXTURE_2D,output);glUniform1i(glGetUniformLocation(stampProgram,"InSampler"),0);
            glDrawArrays(GL_TRIANGLES,0,3);main=read(64,64);
            for(int y=0;y<64;y++)for(int x=0;x<64;x++)for(int c=0;c<4;c++) {
                int expected=x<16 && y>=2 && y<19?retained[((y-2)*16+x)*4+c]:0;
                if(main[(y*64+x)*4+c]!=expected)throw new IllegalStateException("stamp bounds");
            }
            for(int i=0;i<20;i++){int p=(10+i)*4;main[p]=data[i];main[p+1]=57;main[p+2]=143;main[p+3]=211;}
            if(corrupt)main[10*4]^=1;
            // The reordered bank deliberately loses its own history and must recover from Main.
            glUseProgram(cacheProgram);glBindFramebuffer(GL_FRAMEBUFFER,fbo);glViewport(0,0,16,17);block(cacheProgram,"SamplerInfo",0,info);
            texture(0,64,64,main);texture(1,16,17,new int[16*17*4]);glUniform1i(glGetUniformLocation(cacheProgram,"MainSampler"),0);glUniform1i(glGetUniformLocation(cacheProgram,"PreviousSampler"),1);
            glDrawArrays(GL_TRIANGLES,0,3);retained=read(16,17);
            if(!corrupt)expected(reference,data);
            equal(retained,reference,"forwarded packet "+step);checked+=16*17;
        }
        int[] main=new int[64*64*4];for(int y=0;y<17;y++)for(int x=0;x<16;x++)for(int c=0;c<4;c++)main[((y+2)*64+x)*4+c]=retained[(y*16+x)*4+c];
        glUseProgram(overlayProgram);glBindFramebuffer(GL_FRAMEBUFFER,screenFbo);glViewport(0,0,64,64);texture(0,64,64,main);glUniform1i(glGetUniformLocation(overlayProgram,"LiveSampler"),0);glDrawArrays(GL_TRIANGLES,0,3);
        int[] image=read(64,64);
        for(int y=0;y<64;y++)for(int x=0;x<64;x++) {
            int sx=(int)((x+.5)/4),sz=(int)((y+.5)/4);int[] rgb={10,20,30};
            int at=(sz*16+sx)*4;if(retained[at+3]==255)for(int c=0;c<3;c++)rgb[c]=retained[at+c];
            double px=(x+.5-12)/2,py=(64-y-.5-20)/2;
            if(px>=-.3 && px<16.3 && py>=-.3 && py<16.3) {
                rgb=new int[]{20,28,36};
                if(px>=0 && px<16 && py>=0 && py<16){at=((int)py*16+(int)px)*4;if(retained[at+3]==255)for(int c=0;c<3;c++)rgb[c]=retained[at+c];}
            }
            for(int c=0;c<3;c++)if(Math.abs(image[(y*64+x)*4+c]-rgb[c])>1)throw new IllegalStateException("overlay "+x+","+y);
        }
        System.out.println("Live probe: "+checked+" cache pixels exact; two-bank reset recovery, missing/corrupt packets, full replay, revision clearing, stamp bounds, 4096 overlay pixels and both complete shaders OK.");
        glfwDestroyWindow(window);glfwTerminate();
    }
}
