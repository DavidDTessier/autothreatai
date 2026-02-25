<script>
  import { onMount } from 'svelte';

  export let onComplete = () => {};

  let container;

  const colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#f9ca24', '#f0932b', '#eb4d4b', '#6c5ce7', '#a29bfe'];
  const balloonCount = 18;

  onMount(() => {
    if (!container) return;
    container.innerHTML = '';
    const balloons = [];
    for (let i = 0; i < balloonCount; i++) {
      const balloon = document.createElement('div');
      balloon.className = 'balloon';
      balloon.style.left = `${Math.random() * 100}%`;
      balloon.style.animationDelay = `${Math.random() * 0.5}s`;
      balloon.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
      const string = document.createElement('div');
      string.className = 'balloon-string';
      balloon.appendChild(string);
      container.appendChild(balloon);
      balloons.push(balloon);
    }
    setTimeout(() => {
      balloons.forEach((balloon, index) => {
        setTimeout(() => {
          balloon.classList.add('pop');
          setTimeout(() => balloon.remove(), 500);
        }, index * 100 + 2000);
      });
    }, 1000);
    setTimeout(() => onComplete(), 500 + balloonCount * 100 + 2000);
  });
</script>

<div class="balloon-container" bind:this={container} role="presentation" aria-hidden="true"></div>
