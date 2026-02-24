import * as THREE from 'https://unpkg.com/three@0.161.0/build/three.module.js';

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x9fd0ff);
scene.fog = new THREE.Fog(0x9fd0ff, 20, 150);

const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 500);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
document.body.appendChild(renderer.domElement);

const statusEl = document.getElementById('status');

const hemi = new THREE.HemisphereLight(0xffffff, 0x65758a, 0.8);
scene.add(hemi);

const sun = new THREE.DirectionalLight(0xffffff, 1.0);
sun.position.set(25, 40, -20);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
scene.add(sun);

const streetMat = new THREE.MeshStandardMaterial({ color: 0x373737, roughness: 0.95 });
const sidewalkMat = new THREE.MeshStandardMaterial({ color: 0x5f5f5f, roughness: 0.9 });
const wallMat = new THREE.MeshStandardMaterial({ color: 0xb4b4b4, roughness: 0.95 });

const ground = new THREE.Mesh(new THREE.PlaneGeometry(140, 140), streetMat);
ground.rotation.x = -Math.PI / 2;
ground.receiveShadow = true;
scene.add(ground);

const sidewalks = [
  { x: -18, z: 0, w: 16, d: 120 },
  { x: 18, z: 0, w: 16, d: 120 },
];
for (const s of sidewalks) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(s.w, 0.6, s.d), sidewalkMat);
  mesh.position.set(s.x, 0.3, s.z);
  mesh.receiveShadow = true;
  scene.add(mesh);
}

const walls = [];
function addWall(x, y, z, w, h, d) {
  const wall = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), wallMat);
  wall.position.set(x, y, z);
  wall.castShadow = true;
  wall.receiveShadow = true;
  scene.add(wall);
  walls.push({ mesh: wall, half: new THREE.Vector3(w / 2, h / 2, d / 2) });
}

addWall(0, 3, -60, 60, 6, 2);
addWall(0, 3, 60, 60, 6, 2);
addWall(-30, 3, 0, 2, 6, 120);
addWall(30, 3, 0, 2, 6, 120);
addWall(-8, 2.5, -20, 1.5, 5, 14);
addWall(10, 2.5, 14, 1.5, 5, 14);
addWall(-12, 2.5, 32, 1.5, 5, 14);

for (let i = 0; i < 22; i += 1) {
  const b = new THREE.Mesh(
    new THREE.BoxGeometry(8 + Math.random() * 8, 10 + Math.random() * 24, 8 + Math.random() * 8),
    new THREE.MeshStandardMaterial({ color: new THREE.Color().setHSL(0.58, 0.08, 0.45 + Math.random() * 0.24) })
  );
  b.position.set((Math.random() > 0.5 ? -1 : 1) * (36 + Math.random() * 25), b.geometry.parameters.height / 2, -55 + i * 5.2);
  b.castShadow = true;
  b.receiveShadow = true;
  scene.add(b);
}

const keys = { KeyW: false, KeyA: false, KeyS: false, KeyD: false, Space: false };
const player = {
  pos: new THREE.Vector3(0, 1.8, 30),
  vel: new THREE.Vector3(),
  yaw: 0,
  pitch: 0,
  radius: 0.5,
  height: 1.8,
  onGround: false,
  swordCooldown: 0,
};

const frogHand = new THREE.Mesh(
  new THREE.SphereGeometry(0.24, 18, 18),
  new THREE.MeshStandardMaterial({ color: 0x33aa44, roughness: 0.5 })
);
frogHand.position.set(0.55, -0.5, -0.8);
camera.add(frogHand);

const katanaGroup = new THREE.Group();
const handle = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.04, 0.25, 10), new THREE.MeshStandardMaterial({ color: 0x222222 }));
handle.rotation.z = Math.PI / 2;
handle.position.set(0.0, -0.02, 0);
katanaGroup.add(handle);
const blade = new THREE.Mesh(new THREE.BoxGeometry(0.02, 0.68, 0.05), new THREE.MeshStandardMaterial({ color: 0xcde4ff, metalness: 0.8, roughness: 0.2 }));
blade.position.set(0.0, 0.35, 0);
katanaGroup.add(blade);
katanaGroup.position.set(0.42, -0.46, -0.68);
katanaGroup.rotation.set(0.1, 0.15, -0.55);
camera.add(katanaGroup);
scene.add(camera);

const enemies = [];
function createEnemy(position) {
  const group = new THREE.Group();

  const bodyMat = new THREE.MeshStandardMaterial({ color: 0x223b8f });
  const skinMat = new THREE.MeshStandardMaterial({ color: 0xf6d2b0 });
  const hatMat = new THREE.MeshStandardMaterial({ color: 0x1f1f1f });

  const torso = new THREE.Mesh(new THREE.BoxGeometry(0.8, 1.1, 0.42), bodyMat);
  torso.position.y = 1.3;
  torso.castShadow = true;
  group.add(torso);

  const head = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.5, 0.5), skinMat);
  head.position.y = 2.15;
  head.castShadow = true;
  group.add(head);

  const beret = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.36, 0.15, 16), hatMat);
  beret.position.y = 2.45;
  beret.rotation.z = 0.25;
  beret.castShadow = true;
  group.add(beret);

  const legs = new THREE.Mesh(new THREE.BoxGeometry(0.65, 1, 0.32), new THREE.MeshStandardMaterial({ color: 0x111111 }));
  legs.position.y = 0.5;
  legs.castShadow = true;
  group.add(legs);

  group.position.copy(position);
  scene.add(group);

  enemies.push({
    group,
    vel: new THREE.Vector3(),
    radius: 0.55,
    alive: true,
  });
}

for (let i = 0; i < 12; i += 1) {
  createEnemy(new THREE.Vector3(-8 + Math.random() * 16, 0, -40 + i * 6));
}

let slashTimer = 0;
let chargingBubble = false;
let bubbleCharge = 0;
let heldBubble = null;
const projectiles = [];

function spawnHeldBubble() {
  heldBubble = new THREE.Mesh(
    new THREE.SphereGeometry(0.25, 20, 20),
    new THREE.MeshStandardMaterial({ color: 0xff67c7, roughness: 0.35, metalness: 0.12, transparent: true, opacity: 0.78 })
  );
  heldBubble.position.set(0, 0, -2.1);
  camera.add(heldBubble);
}

function launchBubble() {
  if (!heldBubble) return;
  camera.remove(heldBubble);

  const worldPos = new THREE.Vector3();
  heldBubble.getWorldPosition(worldPos);

  const worldQuat = new THREE.Quaternion();
  camera.getWorldQuaternion(worldQuat);
  const dir = new THREE.Vector3(0, 0, -1).applyQuaternion(worldQuat).normalize();

  scene.add(heldBubble);
  heldBubble.position.copy(worldPos);

  const strength = 30 + bubbleCharge * 65;
  const projectile = {
    mesh: heldBubble,
    vel: dir.multiplyScalar(strength),
    radius: 0.4 + bubbleCharge * 1.25,
    life: 4,
  };
  projectile.mesh.scale.setScalar(projectile.radius / 0.4);
  projectiles.push(projectile);

  heldBubble = null;
  bubbleCharge = 0;
}

function clampToWalls(entityPos, radius = 0.45) {
  for (const wall of walls) {
    const wp = wall.mesh.position;
    const h = wall.half;
    const minX = wp.x - h.x - radius;
    const maxX = wp.x + h.x + radius;
    const minZ = wp.z - h.z - radius;
    const maxZ = wp.z + h.z + radius;

    if (entityPos.x > minX && entityPos.x < maxX && entityPos.z > minZ && entityPos.z < maxZ) {
      const dx = Math.min(Math.abs(entityPos.x - minX), Math.abs(entityPos.x - maxX));
      const dz = Math.min(Math.abs(entityPos.z - minZ), Math.abs(entityPos.z - maxZ));
      if (dx < dz) {
        entityPos.x = Math.abs(entityPos.x - minX) < Math.abs(entityPos.x - maxX) ? minX : maxX;
      } else {
        entityPos.z = Math.abs(entityPos.z - minZ) < Math.abs(entityPos.z - maxZ) ? minZ : maxZ;
      }
    }
  }
}

function performSlashHit() {
  const forward = new THREE.Vector3(0, 0, -1).applyAxisAngle(new THREE.Vector3(0, 1, 0), player.yaw);
  for (const enemy of enemies) {
    if (!enemy.alive) continue;
    const toEnemy = enemy.group.position.clone().sub(player.pos);
    const dist = toEnemy.length();
    if (dist > 3.2) continue;
    const angle = forward.angleTo(toEnemy.setY(0).normalize());
    if (angle < 0.9) {
      enemy.alive = false;
      scene.remove(enemy.group);
    }
  }
}

function updatePlayer(dt) {
  const accel = 34;
  const friction = 10;
  const gravity = 28;
  const maxSpeed = 16;

  const forward = new THREE.Vector3(Math.sin(player.yaw), 0, Math.cos(player.yaw) * -1);
  const right = new THREE.Vector3().crossVectors(forward, new THREE.Vector3(0, 1, 0)).negate();

  const wishDir = new THREE.Vector3();
  if (keys.KeyW) wishDir.add(forward);
  if (keys.KeyS) wishDir.sub(forward);
  if (keys.KeyA) wishDir.sub(right);
  if (keys.KeyD) wishDir.add(right);
  wishDir.normalize();

  if (wishDir.lengthSq() > 0) {
    player.vel.x += wishDir.x * accel * dt;
    player.vel.z += wishDir.z * accel * dt;
  }

  const planarVel = new THREE.Vector2(player.vel.x, player.vel.z);
  const speed = planarVel.length();
  if (speed > 0) {
    const drop = Math.max(speed - friction * dt, 0) / speed;
    player.vel.x *= drop;
    player.vel.z *= drop;
  }

  const clamped = new THREE.Vector2(player.vel.x, player.vel.z).clampLength(0, maxSpeed);
  player.vel.x = clamped.x;
  player.vel.z = clamped.y;

  player.vel.y -= gravity * dt;

  if (keys.Space && player.onGround) {
    player.vel.y = 12.5;
    player.onGround = false;
  }

  player.pos.addScaledVector(player.vel, dt);

  if (player.pos.y <= player.height) {
    player.pos.y = player.height;
    player.vel.y = 0;
    player.onGround = true;
  }

  clampToWalls(player.pos, player.radius);

  camera.position.copy(player.pos);
}

function updateWeapons(dt) {
  player.swordCooldown = Math.max(0, player.swordCooldown - dt);
  slashTimer = Math.max(0, slashTimer - dt);

  const slashPhase = slashTimer > 0 ? 1 - slashTimer / 0.2 : 0;
  if (slashTimer > 0) {
    katanaGroup.rotation.z = -0.55 + Math.sin(slashPhase * Math.PI) * 1.2;
    katanaGroup.rotation.y = 0.15 + Math.sin(slashPhase * Math.PI) * 0.55;
  } else {
    katanaGroup.rotation.z = -0.55;
    katanaGroup.rotation.y = 0.15;
  }

  if (chargingBubble && heldBubble) {
    bubbleCharge = Math.min(1, bubbleCharge + dt * 0.85);
    const radius = 0.25 + bubbleCharge * 0.95;
    heldBubble.scale.setScalar(radius / 0.25);
    heldBubble.position.set(0, -0.03 + bubbleCharge * 0.06, -1.7 - bubbleCharge * 0.7);
  }
}

function updateEnemies(dt) {
  for (const enemy of enemies) {
    if (!enemy.alive) continue;
    enemy.vel.y -= 25 * dt;

    const toPlayer = player.pos.clone().sub(enemy.group.position);
    const dist = toPlayer.length();
    if (dist < 22 && dist > 1.6) {
      toPlayer.y = 0;
      toPlayer.normalize();
      enemy.vel.addScaledVector(toPlayer, dt * 3.2);
    }

    enemy.vel.x *= 0.93;
    enemy.vel.z *= 0.93;

    enemy.group.position.addScaledVector(enemy.vel, dt);
    if (enemy.group.position.y < 0) {
      enemy.group.position.y = 0;
      enemy.vel.y = 0;
    }

    clampToWalls(enemy.group.position, enemy.radius);

    const look = player.pos.clone();
    look.y = enemy.group.position.y + 1.6;
    enemy.group.lookAt(look);
  }
}

function updateProjectiles(dt) {
  for (let i = projectiles.length - 1; i >= 0; i -= 1) {
    const p = projectiles[i];
    p.life -= dt;
    p.mesh.position.addScaledVector(p.vel, dt);
    p.vel.multiplyScalar(0.995);

    let destroyed = false;
    for (const wall of walls) {
      const wp = wall.mesh.position;
      const h = wall.half;
      if (
        p.mesh.position.x > wp.x - h.x &&
        p.mesh.position.x < wp.x + h.x &&
        p.mesh.position.y > wp.y - h.y &&
        p.mesh.position.y < wp.y + h.y &&
        p.mesh.position.z > wp.z - h.z &&
        p.mesh.position.z < wp.z + h.z
      ) {
        destroyed = true;
        break;
      }
    }

    for (const enemy of enemies) {
      if (!enemy.alive) continue;
      const d = enemy.group.position.distanceTo(p.mesh.position);
      if (d < enemy.radius + p.radius) {
        const push = enemy.group.position.clone().sub(p.mesh.position).normalize().multiplyScalar(26 + p.radius * 18);
        push.y = 4;
        enemy.vel.add(push);
        destroyed = true;
        break;
      }
    }

    if (destroyed || p.life <= 0) {
      scene.remove(p.mesh);
      projectiles.splice(i, 1);
    }
  }
}

window.addEventListener('keydown', (e) => {
  if (keys[e.code] !== undefined) {
    keys[e.code] = true;
  }
});
window.addEventListener('keyup', (e) => {
  if (keys[e.code] !== undefined) {
    keys[e.code] = false;
  }
});

renderer.domElement.addEventListener('click', () => {
  renderer.domElement.requestPointerLock();
});

document.addEventListener('pointerlockchange', () => {
  if (document.pointerLockElement === renderer.domElement) {
    statusEl.textContent = 'Pointer locked. Hunt the Frenchmen!';
  } else {
    statusEl.textContent = 'Click the game to lock pointer.';
  }
});

document.addEventListener('mousemove', (e) => {
  if (document.pointerLockElement !== renderer.domElement) return;
  player.yaw -= e.movementX * 0.0025;
  player.pitch -= e.movementY * 0.0025;
  player.pitch = Math.max(-1.35, Math.min(1.35, player.pitch));
  camera.rotation.set(player.pitch, player.yaw, 0, 'YXZ');
});

window.addEventListener('mousedown', (e) => {
  if (e.button === 0) {
    if (player.swordCooldown <= 0) {
      slashTimer = 0.2;
      player.swordCooldown = 0.3;
      performSlashHit();
    }
  } else if (e.button === 2) {
    e.preventDefault();
    if (!chargingBubble) {
      chargingBubble = true;
      bubbleCharge = 0;
      spawnHeldBubble();
    }
  }
});

window.addEventListener('mouseup', (e) => {
  if (e.button === 2) {
    if (chargingBubble) {
      chargingBubble = false;
      launchBubble();
    }
  }
});

window.addEventListener('contextmenu', (e) => e.preventDefault());
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

const clock = new THREE.Clock();
function animate() {
  requestAnimationFrame(animate);
  const dt = Math.min(clock.getDelta(), 0.033);
  updatePlayer(dt);
  updateWeapons(dt);
  updateEnemies(dt);
  updateProjectiles(dt);
  renderer.render(scene, camera);
}
animate();
