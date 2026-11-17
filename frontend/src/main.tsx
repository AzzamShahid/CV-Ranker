import {createRoot} from 'react-dom/client';
import App from './app';
const node=document.getElementById('root');
if (!node) throw new Error('Missing application root');
createRoot(node).render(<App/>);
