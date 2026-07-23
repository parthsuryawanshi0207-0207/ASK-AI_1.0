self.addEventListener('install', (event) => {
    console.log('Service worker installing...');
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    console.log('Service worker activating...');
});

self.addEventListener('fetch', (event) => {
    // A simple fetch event handler to satisfy PWA requirements
});
