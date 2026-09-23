import { McpServer } from '@modelcontextprotocol/server';
import { StdioServerTransport } from '@modelcontextprotocol/server/stdio';
import { z } from 'zod';
const server = new McpServer({name:'verification-weather',version:'1.0.0'});
server.registerTool('forecast_mcp', {description:'Return the verified weather for a city.',inputSchema:{city:z.string()}},
  async({city})=>({content:[{type:'text',text:`Sunny in ${city}; 22 C.`}]}));
await server.connect(new StdioServerTransport());
