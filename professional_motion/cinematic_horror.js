import * as THREE from 'three';

// Opt-in v2 rig. Fixed sample count and one shadow map keep CPU rendering bounded.
export function cinematicHorror(renderer, scene, camera, haunted) {
  renderer.shadowMap.enabled=true;
  renderer.shadowMap.type=THREE.PCFSoftShadowMap;
  const key=new THREE.SpotLight(0xc9d7c4,24,24,.86,.76,1.5);
  key.castShadow=true;key.shadow.mapSize.set(512,512);
  key.shadow.bias=-.0006;key.shadow.normalBias=.025;
  key.shadow.camera.near=.3;key.shadow.camera.far=24;
  scene.add(key,key.target);
  haunted.root.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;}});
  const foreground=new THREE.Group();haunted.root.add(foreground);
  const dust=new Float32Array(96*3);
  for(let i=0;i<96;i++){
    dust[i*3]=Math.sin(i*12.9898)*1.9;
    dust[i*3+1]=Math.cos(i*7.233)*1.7;
    dust[i*3+2]=3-(i%24)*.62;
  }
  const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(dust,3));
  const particles=new THREE.Points(geometry,new THREE.PointsMaterial({color:0xb3ba9f,size:.012,transparent:true,opacity:.18,depthWrite:false}));
  foreground.add(particles);
  const base=new THREE.Vector3(),target=new THREE.Vector3(),side=new THREE.Vector3();
  return {
    update(view,mode,p,time){
      // Smooth dolly with modest lateral parallax; preserve the authored subject target.
      const eased=p*p*(3-2*p);
      base.fromArray(view.position);target.fromArray(view.target);
      side.subVectors(target,base).cross(camera.up).normalize();
      const close=['phone','clock','mirror'].includes(mode);
      base.addScaledVector(side,(eased-.5)*(close?.26:.16));
      camera.position.copy(base);camera.lookAt(target);
      key.position.copy(base).add(new THREE.Vector3(-.85,1.45,-.2));
      key.target.position.copy(target);key.intensity=close?20:14;
      // Dust belongs to the corridor's volume and does not cover captions or text.
      foreground.visible=['hall','door','reveal'].includes(mode);
      particles.rotation.y=Math.sin(time*.05)*.035;
      particles.position.y=Math.sin(time*.13)*.045;
      return {version:2,shadow_maps:1,shadow_size:512,dust_points:96,camera:camera.position.toArray()};
    }
  };
}

export function wornSurface(material, kind) {
  const size=64,pixels=new Uint8Array(size*size*4);
  for(let y=0;y<size;y++)for(let x=0;x<size;x++){
    const grain=kind==='wood'?Math.sin(x*.8+Math.sin(y*.13)*2):Math.sin(x*1.7+y*2.1)*Math.cos(y*.9-x*.6);
    const v=Math.round(128+grain*(kind==='metal'?12:24)),i=(y*size+x)*4;
    pixels[i]=pixels[i+1]=pixels[i+2]=v;pixels[i+3]=255;
  }
  const texture=new THREE.DataTexture(pixels,size,size);texture.wrapS=texture.wrapT=THREE.RepeatWrapping;
  texture.magFilter=THREE.LinearFilter;texture.minFilter=THREE.LinearFilter;texture.needsUpdate=true;
  material.bumpMap=texture;material.bumpScale=kind==='metal'?.012:.035;
  material.roughnessMap=texture;material.needsUpdate=true;
}
