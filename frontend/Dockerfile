FROM node:22-alpine
WORKDIR /app
COPY package.json ./
RUN npm install --package-lock=false
COPY tsconfig.json tsconfig.node.json vite.config.ts index.html ./
COPY src ./src
EXPOSE 5173
CMD ["npm", "run", "dev"]
