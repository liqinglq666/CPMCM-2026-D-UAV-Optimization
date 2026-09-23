// AI assistance: ChatGPT/Codex, OpenAI, 2026-09-23; exact model/release unavailable.
import fs from 'node:fs/promises';
import path from 'node:path';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';
const [template, payloadFile, outputDir, mode='preview'] = process.argv.slice(2);
await fs.mkdir(outputDir,{recursive:true});
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(template));
if(mode==='preview') {
 console.log((await wb.inspect({kind:'sheet',include:'id,name',maxChars:2500})).ndjson);
 console.log(wb.help('workbook.render',{include:'index,examples,notes',maxChars:3000}).ndjson);
 const blob=await wb.render({sheetName:'Q1_单点组批',range:'A1:I3',scale:1.3,format:'png'});
 await fs.writeFile(path.join(outputDir,'template_preview.png'),new Uint8Array(await blob.arrayBuffer()));
} else {
 const payload=JSON.parse(await fs.readFile(payloadFile,'utf8'));
 for(const item of payload.sheets) {
  const sheet=item.add?wb.worksheets.add(item.name):wb.worksheets.getItem(item.name);
  const n=item.values.length,m=item.headers.length;
  if(item.add) {
   sheet.getRangeByIndexes(0,0,1,m).values=[item.headers];
   sheet.getRangeByIndexes(0,0,1,m).format.font={name:'FandolHei',bold:true,size:11};
  }
  sheet.getRangeByIndexes(1,0,n,m).values=item.values;
  sheet.getRangeByIndexes(1,0,n,m).format.font={name:'FandolHei',size:10,bold:false};
  sheet.getRangeByIndexes(1,0,n,m).format.rowHeight=25;
  sheet.getRangeByIndexes(1,0,n,m).format.verticalAlignment='center';
  sheet.getRangeByIndexes(1,0,n,m).format.wrapText=true;
  for(let c=0;c<m;c++) {
   const isNumber=item.numeric_columns.includes(c);
   const column=sheet.getRangeByIndexes(0,c,n+1,1);
   const width=item.headers[c].includes('货箱编号列表')?65:item.widths[c];
   column.format.columnWidth=width;
   sheet.getRangeByIndexes(1,c,n,1).format.horizontalAlignment=isNumber?'right':'left';
   if(isNumber) sheet.getRangeByIndexes(1,c,n,1).setNumberFormat(item.formats[c]||'0.000');
  }
  for(let r=0;r<n;r++) {
   const lines=Math.max(...item.values[r].map((value,c)=>{
    const width=item.headers[c].includes('货箱编号列表')?65:item.widths[c];
    const text=String(value??'');
    const units=[...text].reduce((total,char)=>total+(char.charCodeAt(0)>255?2:1),0);
    return Math.ceil(units/(width*.95));
   }));
   sheet.getRangeByIndexes(r+1,0,1,m).format.rowHeight=Math.max(25,lines*16+5);
  }
  sheet.getRangeByIndexes(0,0,1,m).format.rowHeight=36;
  sheet.getRangeByIndexes(0,0,1,m).format.wrapText=true;
  sheet.freezePanes.freezeRows(1);
 }
 wb.recalculate();
 console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#N/A|#NAME\\?|#NUM!',options:{useRegex:true,maxResults:20},maxChars:2000})).ndjson);
 const out=await SpreadsheetFile.exportXlsx(wb);
 await out.save(path.join(outputDir,'D_results.xlsx'));
 for(const item of payload.sheets) {
  const blob=await wb.render({sheetName:item.name,range:`A1:${String.fromCharCode(64+item.headers.length)}${Math.min(item.values.length+1,9)}`,scale:1.2,format:'png'});
  await fs.writeFile(path.join(outputDir,item.name+'.png'),new Uint8Array(await blob.arrayBuffer()));
 }
 console.log('Exported '+payload.sheets.length+' sheets');
}
