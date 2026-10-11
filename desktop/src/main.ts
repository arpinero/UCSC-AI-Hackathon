import { mount } from 'svelte';
import App from './app/App.svelte';
import './lib/llama/app.css';
import './app/pipeline.css';
mount(App, { target: document.getElementById('app')! });
