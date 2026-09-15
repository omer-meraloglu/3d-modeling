// Deterministic software renderer. All shadows and cavities use the real mesh.
#include <algorithm>
#include <cmath>
#include <cstring>
#include <vector>

struct Pixel {float x,y,z,nx,ny,nz;int material=-1;};
static float clamp(float v,float a=0,float b=1){return std::clamp(v,a,b);}

extern "C" void render_mesh(const float* v,const float* n,const float* material,
                            const float* world,const float* heights,int gw,int gh,
                            float gx,float gy,float pitch,
                            int triangles,int width,int height,
                            float vx,float vy,float vz,unsigned char* rgba){
    std::vector<float> depth(size_t(width)*height,-1e30f);
    std::vector<Pixel> pixels(size_t(width)*height);
    std::memset(rgba,0,size_t(width)*height*4);
    auto terrain=[&](float x,float y){
        float fx=(x-gx)/pitch,fy=(y-gy)/pitch;
        int ix=int(std::floor(fx)),iy=int(std::floor(fy));
        if(ix<0||iy<0||ix>=gw-1||iy>=gh-1)return 0.0f;
        float dx=fx-ix,dy=fy-iy;
        return (1-dy)*((1-dx)*heights[iy*gw+ix]+dx*heights[iy*gw+ix+1])+
            dy*((1-dx)*heights[(iy+1)*gw+ix]+dx*heights[(iy+1)*gw+ix+1]);
    };
    for(int f=0;f<triangles;++f){
        const float* p=v+f*9;const float* nn=n+f*9;const float* ww=world+f*9;
        float x0=p[0],y0=p[1],z0=p[2],x1=p[3],y1=p[4],z1=p[5],x2=p[6],y2=p[7],z2=p[8];
        float den=(y1-y2)*(x0-x2)+(x2-x1)*(y0-y2);
        if(den>=-1e-7f)continue;
        int xmin=std::max(0,int(std::floor(std::min({x0,x1,x2}))));
        int xmax=std::min(width-1,int(std::ceil(std::max({x0,x1,x2}))));
        int ymin=std::max(0,int(std::floor(std::min({y0,y1,y2}))));
        int ymax=std::min(height-1,int(std::ceil(std::max({y0,y1,y2}))));
        float inv=1.0f/den;
        for(int y=ymin;y<=ymax;++y)for(int x=xmin;x<=xmax;++x){
            float a=((y1-y2)*(x+.5f-x2)+(x2-x1)*(y+.5f-y2))*inv;
            float b=((y2-y0)*(x+.5f-x2)+(x0-x2)*(y+.5f-y2))*inv;
            float c=1-a-b;
            if(a<-1e-5f||b<-1e-5f||c<-1e-5f)continue;
            float z=a*z0+b*z1+c*z2;int index=y*width+x;
            if(z<=depth[index])continue;depth[index]=z;
            Pixel& out=pixels[index];out.material=f;
            out.x=a*ww[0]+b*ww[3]+c*ww[6];out.y=a*ww[1]+b*ww[4]+c*ww[7];out.z=a*ww[2]+b*ww[5]+c*ww[8];
            out.nx=a*nn[0]+b*nn[3]+c*nn[6];out.ny=a*nn[1]+b*nn[4]+c*nn[7];out.nz=a*nn[2]+b*nn[5]+c*nn[8];
            float norm=1.0f/std::sqrt(out.nx*out.nx+out.ny*out.ny+out.nz*out.nz+1e-20f);
            out.nx*=norm;out.ny*=norm;out.nz*=norm;
        }
    }
    float lx=-.40f,ly=.46f,lz=.793f;
    float hx=vx+lx,hy=vy+ly,hz=vz+lz;
    float hl=std::sqrt(hx*hx+hy*hy+hz*hz);hx/=hl;hy/=hl;hz/=hl;
    const float directions[8][2]={{1,0},{.707f,.707f},{0,1},{-.707f,.707f},{-1,0},{-.707f,-.707f},{0,-1},{.707f,-.707f}};
    for(int index=0;index<width*height;++index){
        const Pixel& p=pixels[index];if(p.material<0)continue;
        const float* mat=material+p.material*5;
        float occlusion=0;
        for(int k=0;k<8;++k){
            float horizon=0;
            for(float r=.30f;r<4.5f;r*=1.60f){
                float dz=terrain(p.x+directions[k][0]*r,p.y+directions[k][1]*r)-p.z-.10f;
                horizon=std::max(horizon,clamp(dz/r));
            }
            occlusion+=horizon;
        }
        float ao=1-occlusion*.085f;
        float shadow=0;
        for(int k=-1;k<=1;++k){
            float xx=p.x+p.nx*.13f,yy=p.y+p.ny*.13f,zz=p.z+.16f;
            bool blocked=false;
            for(float t=.40f;t<15;t+=.48f){
                if(terrain(xx+(lx+k*.12f)*t,yy+(ly-k*.06f)*t)>zz+lz*t){blocked=true;break;}
            }
            shadow+=blocked?.17f:1.0f;
        }
        shadow/=3;
        float key=std::max(0.0f,lx*p.nx+ly*p.ny+lz*p.nz);
        float fill=std::max(0.0f,.55f*p.nx-.57f*p.ny+.61f*p.nz);
        float spec=std::pow(std::max(0.0f,p.nx*hx+p.ny*hy+p.nz*hz),34.0f)*mat[3]*88*shadow;
        float rim=std::pow(1-clamp(p.nx*vx+p.ny*vy+p.nz*vz),3.0f)*.11f;
        float lighting=(.34f*ao+.73f*key*shadow+.18f*fill*ao+rim+mat[4]);
        float patina=1-(1-ao)*.25f;
        for(int channel=0;channel<3;++channel){
            float col=mat[channel]*lighting*patina+spec;
            rgba[index*4+channel]=(unsigned char)clamp(col,0,255);
        }
        rgba[index*4+3]=255;
    }
}

extern "C" void build_heightfield(const float* world,int triangles,int width,int height,float x0,float y0,float pitch,float* out){
    std::fill(out,out+width*height,0.0f);
    for(int f=0;f<triangles;++f){
        const float* p=world+f*9;
        float x[3],y[3];for(int i=0;i<3;++i){x[i]=(p[i*3]-x0)/pitch;y[i]=(p[i*3+1]-y0)/pitch;}
        float den=(y[1]-y[2])*(x[0]-x[2])+(x[2]-x[1])*(y[0]-y[2]);if(std::abs(den)<1e-9f)continue;
        int xa=std::max(0,int(std::floor(std::min({x[0],x[1],x[2]})))),xb=std::min(width-1,int(std::ceil(std::max({x[0],x[1],x[2]}))));
        int ya=std::max(0,int(std::floor(std::min({y[0],y[1],y[2]})))),yb=std::min(height-1,int(std::ceil(std::max({y[0],y[1],y[2]}))));
        for(int iy=ya;iy<=yb;++iy)for(int ix=xa;ix<=xb;++ix){
            float a=((y[1]-y[2])*(ix-x[2])+(x[2]-x[1])*(iy-y[2]))/den;
            float b=((y[2]-y[0])*(ix-x[2])+(x[0]-x[2])*(iy-y[2]))/den;float c=1-a-b;
            if(a>=-1e-5f&&b>=-1e-5f&&c>=-1e-5f)out[iy*width+ix]=std::max(out[iy*width+ix],a*p[2]+b*p[5]+c*p[8]);
        }
    }
}
