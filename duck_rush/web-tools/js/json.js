class JsonExtractResult {
    constructor(json, start, end) {
        this.json = json;
        this.text = text
        this.start = start;
        this.end = end;
    }
}

function extractAllJSONFromText(text) {
    if (!text || typeof text !== 'string') {
        return [];
    }

    const jsonMatches = [];
    let currentJson = '';
    let inString = false;
    let escapeNext = false;
    let braceLevel = 0;
    let bracketLevel = 0;
    let startIndex = -1;

    for (let i = 0; i < text.length; i++) {
        const char = text[i];

        // 处理转义字符
        if (escapeNext) {
            currentJson += char;
            escapeNext = false;
            continue;
        }

        // 处理反斜杠
        if (char === '\\' && inString) {
            currentJson += char;
            escapeNext = true;
            continue;
        }

        // 处理引号
        if (char === '"' && !escapeNext) {
            inString = !inString;
            currentJson += char;
            continue;
        }

        // 只有不在字符串中时才处理括号
        if (!inString) {
            // 处理对象开始
            if (char === '{') {
                if (braceLevel === 0 && bracketLevel === 0) {
                    startIndex = i;
                }
                braceLevel++;
                currentJson += char;
            }
            // 处理对象结束
            else if (char === '}') {
                currentJson += char;
                braceLevel--;
                if (braceLevel === 0 && bracketLevel === 0 && startIndex !== -1) {
                    jsonMatches.push({
                        json: currentJson,
                        start: startIndex,
                        end: i
                    });
                    currentJson = '';
                    startIndex = -1;
                }
            }
            // 处理数组开始
            else if (char === '[') {
                if (braceLevel === 0 && bracketLevel === 0) {
                    startIndex = i;
                }
                bracketLevel++;
                currentJson += char;
            }
            // 处理数组结束
            else if (char === ']') {
                currentJson += char;
                bracketLevel--;
                if (braceLevel === 0 && bracketLevel === 0 && startIndex !== -1) {
                    jsonMatches.push({
                        json: currentJson,
                        start: startIndex,
                        end: i
                    });
                    currentJson = '';
                    startIndex = -1;
                }
            }
            // 处理其他字符
            else {
                if (startIndex !== -1) {
                    currentJson += char;
                }
            }
        }
        // 在字符串中，直接添加字符
        else {
            currentJson += char;
        }
    }

    return jsonMatches;
}

// 导出函数
if (typeof module !== 'undefined' && module.exports) {
    module.exports = extractAllJSONFromText;
}