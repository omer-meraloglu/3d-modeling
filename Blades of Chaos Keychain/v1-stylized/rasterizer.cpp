#include <algorithm>
#include <cmath>
#include <cstring>
#include <vector>

extern "C" void render_mesh(const float* v, const float* n, const float* material,
                            int triangles, int width, int height,
                            float vx, float vy, float vz, unsigned char* rgba) {
    std::vector<float> depth(size_t(width)*height, -1e30f);
    std::memset(rgba, 0, size_t(width)*height*4);
    float hx=vx-.32f, hy=vy-.57f, hz=vz+.757f;
    float hl=std::sqrt(hx*hx+hy*hy+hz*hz); hx/=hl;hy/=hl;hz/=hl;
    for(int f=0;f<triangles;++f){
        const float* p=v+f*9; const float* nn=n+f*9; const float* mat=material+f*5;
        float x0=p[0],y0=p[1],z0=p[2],x1=p[3],y1=p[4],z1=p[5],x2=p[6],y2=p[7],z2=p[8];
        float den=(y1-y2)*(x0-x2)+(x2-x1)*(y0-y2);
        if(den>=-1e-6f)continue;
        int xmin=std::max(0,int(std::floor(std::min({x0,x1,x2}))));
        int xmax=std::min(width-1,int(std::ceil(std::max({x0,x1,x2}))));
        int ymin=std::max(0,int(std::floor(std::min({y0,y1,y2}))));
        int ymax=std::min(height-1,int(std::ceil(std::max({y0,y1,y2}))));
        float inv=1.0f/den;
        for(int y=ymin;y<=ymax;++y){
            for(int x=xmin;x<=xmax;++x){
                float a=((y1-y2)*(x+.5f-x2)+(x2-x1)*(y+.5f-y2))*inv;
                float b=((y2-y0)*(x+.5f-x2)+(x0-x2)*(y+.5f-y2))*inv;
                float c=1-a-b;
                if(a< -1e-5f||b< -1e-5f||c< -1e-5f)continue;
                float z=a*z0+b*z1+c*z2;int index=y*width+x;
                if(z<=depth[index])continue;depth[index]=z;
                float nx=a*nn[0]+b*nn[3]+c*nn[6];
                float ny=a*nn[1]+b*nn[4]+c*nn[7];
                float nz=a*nn[2]+b*nn[5]+c*nn[8];
                float norm=1.0f/std::sqrt(nx*nx+ny*ny+nz*nz+1e-20f);
                nx*=norm;ny*=norm;nz*=norm;
                float key=std::max(0.0f,-.32f*nx-.57f*ny+.757f*nz);
                float fill=std::max(0.0f,.80f*nx+.12f*ny+.588f*nz);
                float spec=std::pow(std::max(0.0f,nx*hx+ny*hy+nz*hz),40.0f)*mat[3]*140;
                float rim=std::pow(1-std::max(0.0f,nx*vx+ny*vy+nz*vz),3.0f)*.10f;
                float lighting=.39f+.58f*key+.16f*fill+rim+mat[4];
                for(int channel=0;channel<3;++channel)
                    rgba[index*4+channel]=(unsigned char)std::clamp(mat[channel]*lighting+spec,0.0f,255.0f);
                rgba[index*4+3]=255;
            }
        }
    }
}
