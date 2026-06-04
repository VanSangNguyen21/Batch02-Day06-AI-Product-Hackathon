'use strict';

document.addEventListener('DOMContentLoaded', () => {
  const params = new URLSearchParams(window.location.search);
  if (params.get('next') === 'main') {
    window.location.href = 'auth.html?mode=login';
    return;
  }

  initLearningPathScene();
});

function initLearningPathScene() {
  const canvas = document.getElementById('landing-3d-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!ctx) return;

  const state = {
    width: 0,
    height: 0,
    dpr: 1,
    time: 0,
    mouseX: 0,
    mouseY: 0,
    targetX: 0,
    targetY: 0,
    particles: [],
  };

  const stages = [
    { key: 'goal', step: '01', label: 'Goal Input', sub: 'Muc tieu + lich hoc', x: -390, y: -82, z: -120, color: '#72f5d1' },
    { key: 'quiz', step: '02', label: 'Skill Quiz', sub: '10 cau danh gia', x: -205, y: 66, z: 70, color: '#a78bfa' },
    { key: 'ai', step: '03', label: 'AI Analysis', sub: 'Ca nhan hoa', x: 0, y: -18, z: 185, color: '#67e8f9', core: true },
    { key: 'roadmap', step: '04', label: 'Roadmap', sub: 'Lo trinh hoc', x: 210, y: 78, z: 25, color: '#60a5fa' },
    { key: 'chat', step: '05', label: 'AI Coach', sub: 'Chat ho tro', x: 400, y: -76, z: -135, color: '#fbbf24' },
  ];

  function resize() {
    state.dpr = Math.min(window.devicePixelRatio || 1, 2);
    state.width = window.innerWidth;
    state.height = window.innerHeight;
    canvas.width = Math.floor(state.width * state.dpr);
    canvas.height = Math.floor(state.height * state.dpr);
    canvas.style.width = `${state.width}px`;
    canvas.style.height = `${state.height}px`;
    ctx.setTransform(state.dpr, 0, 0, state.dpr, 0, 0);
    buildParticles();
  }

  function buildParticles() {
    const count = state.width < 760 ? 26 : 48;
    state.particles = Array.from({ length: count }, (_, index) => ({
      progress: index / count,
      lane: (index % 5) - 2,
      speed: 0.0016 + (index % 4) * 0.00035,
      radius: 1.2 + (index % 3) * 0.45,
    }));
  }

  function rotate(point, rx, ry) {
    const cx = Math.cos(rx), sx = Math.sin(rx);
    const cy = Math.cos(ry), sy = Math.sin(ry);
    let x = point.x;
    let y = point.y * cx - point.z * sx;
    let z = point.y * sx + point.z * cx;
    const x2 = x * cy + z * sy;
    z = -x * sy + z * cy;
    x = x2;
    return { ...point, x, y, z };
  }

  function project(point) {
    const camera = Math.max(state.width, state.height) * 1.25;
    const scale = camera / (camera - point.z);
    return {
      ...point,
      sx: state.width * 0.66 + point.x * scale,
      sy: state.height * 0.51 + point.y * scale,
      scale,
    };
  }

  function transform(point) {
    const rx = -0.18 + state.mouseY * 0.14;
    const ry = Math.sin(state.time * 0.35) * 0.12 + state.mouseX * 0.22;
    return project(rotate(point, rx, ry));
  }

  function pathPoint(progress, lane = 0) {
    const maxIndex = stages.length - 1;
    const scaled = progress * maxIndex;
    const index = Math.min(maxIndex - 1, Math.floor(scaled));
    const local = scaled - index;
    const a = stages[index];
    const b = stages[index + 1];
    const ease = local * local * (3 - 2 * local);
    return {
      x: a.x + (b.x - a.x) * ease,
      y: a.y + (b.y - a.y) * ease + Math.sin(local * Math.PI) * (34 + lane * 5),
      z: a.z + (b.z - a.z) * ease + lane * 20,
    };
  }

  function drawLine(a, b, alpha = 1) {
    const gradient = ctx.createLinearGradient(a.sx, a.sy, b.sx, b.sy);
    gradient.addColorStop(0, `rgba(114,245,209,${0.04 * alpha})`);
    gradient.addColorStop(0.5, `rgba(103,232,249,${0.28 * alpha})`);
    gradient.addColorStop(1, `rgba(96,165,250,${0.05 * alpha})`);
    ctx.strokeStyle = gradient;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(a.sx, a.sy);
    ctx.lineTo(b.sx, b.sy);
    ctx.stroke();
  }

  function drawNode(node) {
    const pulse = 0.75 + Math.sin(state.time * 2.2 + node.x * 0.01) * 0.18;
    const radius = (node.core ? 28 : 19) * node.scale;
    const halo = radius * (2.4 + pulse);

    const glow = ctx.createRadialGradient(node.sx, node.sy, 0, node.sx, node.sy, halo);
    glow.addColorStop(0, `${hexToRgba(node.color, 0.48)}`);
    glow.addColorStop(0.35, `${hexToRgba(node.color, 0.16)}`);
    glow.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(node.sx, node.sy, halo, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = 'rgba(13, 15, 40, 0.82)';
    ctx.strokeStyle = hexToRgba(node.color, 0.82);
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.arc(node.sx, node.sy, radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = node.color;
    ctx.font = `${Math.round((node.core ? 16 : 12) * node.scale)}px Noto Sans, Arial`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(node.core ? 'AI' : node.step, node.sx, node.sy);

    if (state.width >= 760) {
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.font = '700 13px Noto Sans, Arial';
      ctx.fillStyle = 'rgba(245, 247, 255, 0.9)';
      ctx.fillText(node.label, node.sx, node.sy + radius + 12);
      ctx.font = '500 11px Noto Sans, Arial';
      ctx.fillStyle = 'rgba(184, 193, 225, 0.68)';
      ctx.fillText(node.sub, node.sx, node.sy + radius + 30);
    }
  }

  function drawParticle(particle) {
    particle.progress = (particle.progress + particle.speed * (reducedMotion ? 0 : 1)) % 1;
    const point = transform(pathPoint(particle.progress, particle.lane));
    const alpha = 0.28 + Math.sin(particle.progress * Math.PI) * 0.44;
    ctx.fillStyle = `rgba(255,255,255,${alpha})`;
    ctx.beginPath();
    ctx.arc(point.sx, point.sy, particle.radius * point.scale * 1.8, 0, Math.PI * 2);
    ctx.fill();
  }

  function drawDashboardGhost(nodes) {
    if (state.width < 840) return;
    const ai = nodes[2];
    const x = ai.sx - 76;
    const y = ai.sy - 130;
    ctx.save();
    ctx.globalAlpha = 0.24;
    ctx.strokeStyle = 'rgba(167,139,250,0.38)';
    ctx.fillStyle = 'rgba(18,20,54,0.54)';
    roundRect(x, y, 152, 76, 10);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = 'rgba(103,232,249,0.9)';
    ctx.font = '700 11px Noto Sans, Arial';
    ctx.textAlign = 'left';
    ctx.fillText('Personalized learning path', x + 16, y + 16);
    ctx.fillStyle = 'rgba(255,255,255,0.34)';
    for (let i = 0; i < 3; i += 1) {
      ctx.fillRect(x + 16, y + 30 + i * 13, 110 - i * 20, 4);
    }
    ctx.restore();
  }

  function draw() {
    state.time += reducedMotion ? 0 : 0.012;
    state.mouseX += (state.targetX - state.mouseX) * 0.045;
    state.mouseY += (state.targetY - state.mouseY) * 0.045;
    ctx.clearRect(0, 0, state.width, state.height);

    const nodes = stages.map(transform);
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';

    for (let i = 0; i < nodes.length - 1; i += 1) {
      drawLine(nodes[i], nodes[i + 1], 1);
    }

    state.particles.forEach(drawParticle);
    drawDashboardGhost(nodes);
    nodes.sort((a, b) => a.z - b.z).forEach(drawNode);
    ctx.restore();

    if (!reducedMotion) window.requestAnimationFrame(draw);
  }

  function roundRect(x, y, width, height, radius) {
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + width - radius, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
    ctx.lineTo(x + width, y + height - radius);
    ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
    ctx.lineTo(x + radius, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
    ctx.lineTo(x, y + radius);
    ctx.quadraticCurveTo(x, y, x + radius, y);
  }

  function hexToRgba(hex, alpha) {
    const value = hex.replace('#', '');
    const r = parseInt(value.slice(0, 2), 16);
    const g = parseInt(value.slice(2, 4), 16);
    const b = parseInt(value.slice(4, 6), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  }

  window.addEventListener('resize', resize);
  window.addEventListener('mousemove', (event) => {
    state.targetX = (event.clientX / state.width - 0.5) * 2;
    state.targetY = (event.clientY / state.height - 0.5) * 2;
  });

  resize();
  draw();
}
