const user = (await (await fetch("/api/me", { credentials: "include" })).json()).user;

if (!user) {
    throw ReferenceError("The user was not found!");
}


function getDiscordAvatarURL(user) {
    const format = user.avatar.startsWith("a_") ? "gif" : "png"; // animated or static
    const size = 64; // you can use 32, 64, 128, 256, 512, 1024, 2048
    return `https://cdn.discordapp.com/avatars/${user.id}/${user.avatar}.${format}?size=${size}`;
}


const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");

function resizeCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
}

resizeCanvas();
window.addEventListener("resize", resizeCanvas);

const camera = { x: 0, y: 0 };
const player = { x: 100, y: 100, dx: 0, dy: 0, speed: 200, sprite: null };

// Load sprite
const playerImg = new Image();
playerImg.src = getDiscordAvatarURL(user);
playerImg.onload = () => { player.sprite = playerImg; };


const keys = {};

window.addEventListener("keydown", (e) => {
    keys[e.key.toLowerCase()] = true; // store the key as lowercase
});

window.addEventListener("keyup", (e) => {
    keys[e.key.toLowerCase()] = false;
});

let gamepads = {};

window.addEventListener("gamepadconnected", (e) => {
    console.log("Gamepad connected:", e.gamepad);
    gamepads[e.gamepad.index] = e.gamepad;
});

window.addEventListener("gamepaddisconnected", (e) => {
    console.log("Gamepad disconnected:", e.gamepad);
    delete gamepads[e.gamepad.index];
});



function drawRoundAvatar(ctx, img, x, y, size) {
    ctx.save(); // Save the current canvas state

    // Create a circular clipping region
    ctx.beginPath();
    ctx.arc(x + size / 2, y + size / 2, size / 2, 0, Math.PI * 2);
    ctx.closePath();
    ctx.clip();

    // Draw the avatar image inside the clipped circle
    ctx.drawImage(img, x, y, size, size);

    ctx.restore(); // Restore canvas state
}



// Game loop
let lastTime = 0;
function gameLoop(timestamp) {
    const dTime = (timestamp - lastTime) / 1000; // seconds
    lastTime = timestamp;


    ctx.clearRect(0, 0, canvas.width, canvas.height);

    player.dx = 0;
    player.dy = 0;
    if (keys["w"] || keys["arrowup"]) player.dy = -player.speed;
    if (keys["s"] || keys["arrowdown"]) player.dy = player.speed;
    if (keys["a"] || keys["arrowleft"]) player.dx = -player.speed;
    if (keys["d"] || keys["arrowright"]) player.dx = player.speed;

    const gps = navigator.getGamepads();
    for (const gp of gps) {
        if (!gp) continue;

        // Example: move player with left stick
        const [xAxis, yAxis] = [gp.axes[0], gp.axes[1]];

        if (Math.abs(xAxis) > 0.1) player.dx = xAxis * player.speed;
        if (Math.abs(yAxis) > 0.1) player.dy = yAxis * player.speed;
    }

    player.x += player.dx * dTime
    player.y += player.dy * dTime

    // Draw player
    if (player.sprite) {
        drawRoundAvatar(ctx, player.sprite, player.x, player.y, 64)
    }

    requestAnimationFrame(gameLoop);
}

requestAnimationFrame(gameLoop);