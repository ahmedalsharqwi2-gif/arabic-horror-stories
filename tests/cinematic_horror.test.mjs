import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from '../professional_motion/node_modules/three/build/three.module.js';
import {cinematicHorror,wornSurface} from '../professional_motion/cinematic_horror.js';

test('surface relief is deterministic and stays bounded without external textures',()=>{
 const first=new THREE.MeshStandardMaterial(),second=new THREE.MeshStandardMaterial();
 wornSurface(first,'wood');wornSurface(second,'wood');
 assert.deepEqual(first.bumpMap.image.data,second.bumpMap.image.data);
 assert.equal(first.bumpMap.image.width,64);
 assert.ok(first.bumpScale>0&&first.bumpScale<.05);
 assert.ok(new Set(first.bumpMap.image.data).size>20);
});

test('cinematic camera is deterministic when partitions render out of order',()=>{
 const renderer={shadowMap:{}},scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera();
 const root=new THREE.Group();scene.add(root);
 const mesh=new THREE.Mesh(new THREE.BoxGeometry(),new THREE.MeshStandardMaterial());root.add(mesh);
 const vertexCount=mesh.geometry.attributes.position.count;
 const rig=cinematicHorror(renderer,scene,camera,{root});
 const view={position:[0,.25,3.5],target:[0,.25,-12]};
 const first=rig.update(view,'hall',.7,12);
 rig.update(view,'mirror',.2,4);
 const again=rig.update(view,'hall',.7,12);
 assert.deepEqual(first,again);
 assert.ok(camera.position.distanceTo(new THREE.Vector3(...view.position))<.1);
 const direction=camera.getWorldDirection(new THREE.Vector3());
 const expected=new THREE.Vector3(...view.target).sub(camera.position).normalize();
 assert.ok(direction.distanceTo(expected)<1e-10);
 assert.equal(mesh.geometry.attributes.position.count,vertexCount);
 assert.ok(mesh.castShadow&&mesh.receiveShadow);
 assert.equal(scene.children.filter(o=>o.isLight&&o.castShadow).length,1);
});

test('all authored views keep camera values finite across the scene interval',()=>{
 const renderer={shadowMap:{}},scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(),root=new THREE.Group();scene.add(root);
 const rig=cinematicHorror(renderer,scene,camera,{root});
 for(const mode of ['hall','door','phone','mirror','stairs','lift','clock','reveal'])for(const p of [0,.001,.5,.999,1]){
  const result=rig.update({position:[0,1,5],target:[0,0,-1]},mode,p,p*150);
  assert.ok(result.camera.every(Number.isFinite));
 }
});
