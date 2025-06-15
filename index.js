const express = require('express');
const TelegramBot = require('node-telegram-bot-api');
const { GoogleSpreadsheet } = require('google-spreadsheet');
const { JWT } = require('google-auth-library');
const moment = require('moment-timezone');
const cron = require('node-cron');

const app = express();
app.use(express.json());

// Environment variables
const TOKEN_BOT1 = process.env.TOKEN_BOT1;
const TOKEN_BOT2 = process.env.TOKEN_BOT2;
const SHEET_ID = process.env.SHEET_ID;
const GOOGLE_PRIVATE_KEY = process.env.GOOGLE_PRIVATE_KEY?.replace(/\\n/g, '\n');
const GOOGLE_CLIENT_EMAIL = process.env.GOOGLE_CLIENT_EMAIL;
const VERCEL_DOMAIN = process.env.VERCEL_DOMAIN || 'belanjakubot.vercel.app';

// Initialize bots
const bot1 = new TelegramBot(TOKEN_BOT1);
const bot2 = new TelegramBot(TOKEN_BOT2);

// Set timezone
moment.tz.setDefault('Asia/Kuala_Lumpur');

// User sessions untuk tracking conversation state
const userSessions = new Map();

// Google Sheets setup
const serviceAccountAuth = new JWT({
  email: GOOGLE_CLIENT_EMAIL,
  key: GOOGLE_PRIVATE_KEY,
  scopes: ['https://www.googleapis.com/auth/spreadsheets']
});

const doc = new GoogleSpreadsheet(SHEET_ID, serviceAccountAuth);

// Initialize Google Sheets
async function initializeSheet() {
  try {
    await doc.loadInfo();
    console.log('✅ Google Sheets connected successfully');
    
    // Ensure required sheets exist
    const sheetTitles = doc.sheetsByIndex.map(sheet => sheet.title);
    const requiredSheets = ['Expenses', 'Users', 'Reports'];
    
    for (const sheetTitle of requiredSheets) {
      if (!sheetTitles.includes(sheetTitle)) {
        await doc.addSheet({ title: sheetTitle });
        console.log(`📄 Created sheet: ${sheetTitle}`);
      }
    }
    
    // Setup headers for Expenses sheet
    const expenseSheet = doc.sheetsByTitle['Expenses'];
    const headerRow = await expenseSheet.getRows();
    if (headerRow.length === 0) {
      await expenseSheet.setHeaderRow([
        'Date', 'Time', 'User_ID', 'Username', 'Item', 'Amount', 'Location', 'Category', 'Photo_URL', 'Notes'
      ]);
    }
    
    // Setup headers for Users sheet
    const userSheet = doc.sheetsByTitle['Users'];
    const userHeaderRow = await userSheet.getRows();
    if (userHeaderRow.length === 0) {
      await userSheet.setHeaderRow([
        'User_ID', 'Username', 'First_Name', 'Last_Name', 'Join_Date', 'Last_Active', 'Total_Expenses'
      ]);
    }
    
  } catch (error) {
    console.error('❌ Error initializing Google Sheets:', error);
  }
}

// BOT 1 - Expense Input Bot
const setupBot1 = () => {
  // Welcome message
  bot1.onText(/\/start/, async (msg) => {
    const chatId = msg.chat.id;
    const user = msg.from;
    
    await registerUser(user);
    
    const welcomeMessage = `
🎉 *Selamat datang ke LaporBelanjaBot!* 🎉

Helo ${user.first_name}! 👋

Saya adalah bot pintar untuk membantu anda jejak belanja harian. Dengan saya, anda boleh:

💰 Rekod semua belanja dengan mudah
📊 Dapat laporan harian, mingguan & bulanan
📸 Upload resit untuk rekod yang lebih teliti
📍 Simpan lokasi pembelian

*Cara guna:*
• Taip belanja seperti: "Nasi ayam RM10.50"
• Atau gunakan format: "Makan tengahari RM15 di Restoran ABC"
• Upload gambar resit (optional)

*Arahan tersedia:*
/help - Panduan lengkap
/status - Semak status bot
/laporan - Lihat summary belanja
/cancel - Batal operasi semasa

Bot ini dibangunkan oleh *Fadirul Ezwan* 🚀

Mari mulakan jejak belanja anda! Taip apa yang anda beli hari ini 😊
    `;
    
    await bot1.sendMessage(chatId, welcomeMessage, { parse_mode: 'Markdown' });
  });

  // Help command
  bot1.onText(/\/help/, async (msg) => {
    const chatId = msg.chat.id;
    const helpMessage = `
📚 *Panduan Penggunaan LaporBelanjaBot*

*Format Input Belanja:*
• "Nasi ayam RM10.50" 
• "Makan tengahari RM15 di Restoran ABC"
• "Groceries RM45.80 Tesco"
• "Petrol RM60"

*Arahan Tersedia:*
/start - Mula semula
/help - Panduan ini
/status - Semak status bot
/laporan - Lihat ringkasan belanja
/cancel - Batal operasi semasa
/reset - Reset data sesi

*Tips Berguna:*
• Bot akan tanya lokasi jika tidak dinyatakan
• Upload gambar resit untuk rekod yang lebih baik
• Gunakan /cancel untuk membatalkan input
• Bot akan beri cadangan kategori automatik

*Laporan Automatik:*
📅 Harian - 8:00 PM setiap hari
📅 Mingguan - 8:00 PM setiap Ahad  
📅 Bulanan - 8:00 PM setiap 1hb

Sebarang masalah? Hubungi pembangun: *Fadirul Ezwan* ⚡

Selamat menjejak belanja! 💪
    `;
    
    await bot1.sendMessage(chatId, helpMessage, { parse_mode: 'Markdown' });
  });

  // Status command
  bot1.onText(/\/status/, async (msg) => {
    const chatId = msg.chat.id;
    const uptime = process.uptime();
    const hours = Math.floor(uptime / 3600);
    const minutes = Math.floor((uptime % 3600) / 60);
    
    const statusMessage = `
🟢 *Status Bot - AKTIF*

⏰ Bot telah berjalan: ${hours}j ${minutes}m
📊 Google Sheets: Tersambung ✅
🔄 Sistem: Berfungsi Normal
🕐 Masa Semasa: ${moment().format('DD/MM/YYYY HH:mm:ss')}

*Statistik Harian:*
📝 Rekod hari ini: ${await getTodayExpenseCount(msg.from.id)}
💰 Jumlah belanja: RM${await getTodayExpenseTotal(msg.from.id)}

Bot siap membantu anda! 🚀
    `;
    
    await bot1.sendMessage(chatId, statusMessage, { parse_mode: 'Markdown' });
  });

  // Cancel command
  bot1.onText(/\/cancel/, async (msg) => {
    const chatId = msg.chat.id;
    userSessions.delete(chatId);
    await bot1.sendMessage(chatId, '❌ Operasi dibatalkan. Sila mulakan semula dengan menaip belanja anda.');
  });

  // Laporan command
  bot1.onText(/\/laporan/, async (msg) => {
    const chatId = msg.chat.id;
    const userId = msg.from.id;
    
    const today = await getTodayExpenseTotal(userId);
    const week = await getWeekExpenseTotal(userId);
    const month = await getMonthExpenseTotal(userId);
    
    const reportMessage = `
📊 *Ringkasan Belanja Anda*

*Hari Ini (${moment().format('DD/MM/YYYY')}):*
💰 RM${today}

*Minggu Ini:*
💰 RM${week}

*Bulan Ini (${moment().format('MMMM YYYY')}):*
💰 RM${month}

📈 Purata harian bulan ini: RM${(month / moment().date()).toFixed(2)}

Teruskan jejak belanja anda! 💪
    `;
    
    await bot1.sendMessage(chatId, reportMessage, { parse_mode: 'Markdown' });
  });

  // Handle expense input
  bot1.on('message', async (msg) => {
    const chatId = msg.chat.id;
    const userId = msg.from.id;
    const text = msg.text;
    
    // Skip if command
    if (text && text.startsWith('/')) return;
    
    // Handle photo upload
    if (msg.photo) {
      const session = userSessions.get(chatId);
      if (session && session.waitingForPhoto) {
        const photo = msg.photo[msg.photo.length - 1];
        const fileLink = await bot1.getFileLink(photo.file_id);
        session.photoUrl = fileLink;
        session.waitingForPhoto = false;
        
        await bot1.sendMessage(chatId, '📸 Gambar diterima! Sekarang sila taip sebarang nota tambahan atau taip "selesai" untuk simpan.');
        session.waitingForNotes = true;
        return;
      }
    }
    
    // Handle location
    if (msg.location) {
      const session = userSessions.get(chatId);
      if (session && session.waitingForLocation) {
        session.location = `${msg.location.latitude},${msg.location.longitude}`;
        session.waitingForLocation = false;
        
        await bot1.sendMessage(chatId, '📍 Lokasi diterima! Ada apa-apa lagi yang dibeli? Taip "tidak" jika sudah selesai.');
        session.waitingForAdditionalItems = true;
        return;
      }
    }
    
    if (!text) return;
    
    // Handle session states
    const session = userSessions.get(chatId);
    
    if (session) {
      if (session.waitingForLocation) {
        session.location = text;
        session.waitingForLocation = false;
        
        await bot1.sendMessage(chatId, '📍 Lokasi diterima! Ada apa-apa lagi yang dibeli? Taip "tidak" jika sudah selesai.');
        session.waitingForAdditionalItems = true;
        return;
      }
      
      if (session.waitingForAdditionalItems) {
        if (text.toLowerCase() === 'tidak' || text.toLowerCase() === 'selesai') {
          await bot1.sendMessage(chatId, '📸 Boleh upload gambar resit? (Optional - taip "skip" untuk langkau)');
          session.waitingForPhoto = true;
          return;
        } else {
          // Parse additional item
          const parsed = parseExpenseText(text);
          if (parsed) {
            session.additionalItems = session.additionalItems || [];
            session.additionalItems.push(parsed);
            await bot1.sendMessage(chatId, `✅ Ditambah: ${parsed.item} - RM${parsed.amount}\n\nAda lagi? Taip "tidak" jika sudah selesai.`);
            return;
          }
        }
      }
      
      if (session.waitingForPhoto) {
        if (text.toLowerCase() === 'skip') {
          session.waitingForPhoto = false;
          await saveExpenseToSheet(userId, msg.from, session);
          userSessions.delete(chatId);
          await bot1.sendMessage(chatId, '✅ Belanja berjaya disimpan! Taip belanja seterusnya bila-bila masa.');
          return;
        }
      }
      
      if (session.waitingForNotes) {
        if (text.toLowerCase() === 'selesai') {
          session.waitingForNotes = false;
        } else {
          session.notes = text;
        }
        
        await saveExpenseToSheet(userId, msg.from, session);
        userSessions.delete(chatId);
        await bot1.sendMessage(chatId, '✅ Belanja berjaya disimpan dengan lengkap! Taip belanja seterusnya bila-bila masa.');
        return;
      }
    }
    
    // Parse new expense
    const parsed = parseExpenseText(text);
    if (parsed) {
      const newSession = {
        item: parsed.item,
        amount: parsed.amount,
        location: parsed.location,
        category: parsed.category,
        timestamp: new Date()
      };
      
      userSessions.set(chatId, newSession);
      
      if (!parsed.location) {
        await bot1.sendMessage(chatId, `💰 Rekod: ${parsed.item} - RM${parsed.amount}\n\n📍 Di mana anda membelinya? (Taip nama tempat atau hantar lokasi)`);
        newSession.waitingForLocation = true;
      } else {
        await bot1.sendMessage(chatId, `💰 Rekod: ${parsed.item} - RM${parsed.amount}\n📍 Lokasi: ${parsed.location}\n\nAda apa-apa lagi yang dibeli? Taip "tidak" jika sudah selesai.`);
        newSession.waitingForAdditionalItems = true;
      }
    } else {
      await bot1.sendMessage(chatId, `🤔 Maaf, saya tidak faham format itu.\n\n💡 Contoh yang betul:\n• "Nasi ayam RM10.50"\n• "Makan tengahari RM15 di Restoran ABC"\n• "Groceries RM45.80"\n\nSila cuba lagi!`);
    }
  });

  // Set webhook for bot1
  const webhook1Url = `https://${VERCEL_DOMAIN}/webhook/bot1`;
  bot1.setWebHook(webhook1Url);
};

// BOT 2 - Reporting Bot
const setupBot2 = () => {
  bot2.onText(/\/start/, async (msg) => {
    const chatId = msg.chat.id;
    const user = msg.from;
    
    const welcomeMessage = `
📊 *Selamat datang ke LaporanBelanjaBot!* 📊

Helo ${user.first_name}! 👋

Saya adalah bot laporan pintar yang akan memberikan anda analisa mendalam tentang belanja anda.

*Apa yang saya boleh lakukan:*
📈 Laporan harian, mingguan & bulanan
💹 Analisa trend belanja
🏆 Kategori belanja terbanyak
📊 Graf dan statistik
⚡ Laporan real-time

*Arahan tersedia:*
/laporan_hari - Laporan hari ini
/laporan_minggu - Laporan minggu ini  
/laporan_bulan - Laporan bulan ini
/analisa - Analisa mendalam
/trending - Trend belanja
/help - Panduan lengkap

Bot ini dibangunkan oleh *Fadirul Ezwan* 🚀

Sila pilih jenis laporan yang anda mahu! 📊
    `;
    
    await bot2.sendMessage(chatId, welcomeMessage, { parse_mode: 'Markdown' });
  });

  bot2.onText(/\/laporan_hari/, async (msg) => {
    const chatId = msg.chat.id;
    const userId = msg.from.id;
    
    const report = await generateDailyReport(userId);
    await bot2.sendMessage(chatId, report, { parse_mode: 'Markdown' });
  });

  bot2.onText(/\/laporan_minggu/, async (msg) => {
    const chatId = msg.chat.id;
    const userId = msg.from.id;
    
    const report = await generateWeeklyReport(userId);
    await bot2.sendMessage(chatId, report, { parse_mode: 'Markdown' });
  });

  bot2.onText(/\/laporan_bulan/, async (msg) => {
    const chatId = msg.chat.id;
    const userId = msg.from.id;
    
    const report = await generateMonthlyReport(userId);
    await bot2.sendMessage(chatId, report, { parse_mode: 'Markdown' });
  });

  bot2.onText(/\/analisa/, async (msg) => {
    const chatId = msg.chat.id;
    const userId = msg.from.id;
    
    const analysis = await generateAnalysis(userId);
    await bot2.sendMessage(chatId, analysis, { parse_mode: 'Markdown' });
  });

  // Set webhook for bot2
  const webhook2Url = `https://${VERCEL_DOMAIN}/webhook/bot2`;
  bot2.setWebHook(webhook2Url);
};

// Utility Functions
function parseExpenseText(text) {
  // Parse patterns like "Nasi ayam RM10.50", "Makan RM15 di Restoran"
  const patterns = [
    /^(.+?)\s+rm\s*(\d+(?:\.\d{2})?)\s*(?:di\s+(.+))?$/i,
    /^(.+?)\s+(\d+(?:\.\d{2})?)\s*(?:di\s+(.+))?$/i,
    /^(.+?)\s+rm\s*(\d+(?:\.\d{2})?)\s+(.+)$/i
  ];
  
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match) {
      const item = match[1].trim();
      const amount = parseFloat(match[2]);
      const location = match[3] ? match[3].trim() : null;
      const category = categorizeExpense(item);
      
      return { item, amount, location, category };
    }
  }
  
  return null;
}

function categorizeExpense(item) {
  const categories = {
    'Makan & Minum': ['nasi', 'makan', 'minum', 'kopi', 'teh', 'restoran', 'makanan', 'sarapan', 'lunch', 'dinner'],
    'Pengangkutan': ['petrol', 'minyak', 'grab', 'taxi', 'bus', 'tol', 'parking'],
    'Groceries': ['groceries', 'pasar', 'sayur', 'buah', 'daging', 'ikan', 'beras'],
    'Kesihatan': ['ubat', 'hospital', 'klinik', 'doktor', 'vitamin'],
    'Hiburan': ['wayang', 'game', 'movie', 'entertainment'],
    'Lain-lain': []
  };
  
  const itemLower = item.toLowerCase();
  
  for (const [category, keywords] of Object.entries(categories)) {
    if (keywords.some(keyword => itemLower.includes(keyword))) {
      return category;
    }
  }
  
  return 'Lain-lain';
}

async function registerUser(user) {
  try {
    const userSheet = doc.sheetsByTitle['Users'];
    const rows = await userSheet.getRows();
    
    const existingUser = rows.find(row => row.User_ID === user.id.toString());
    
    if (!existingUser) {
      await userSheet.addRow({
        User_ID: user.id.toString(),
        Username: user.username || '',
        First_Name: user.first_name || '',
        Last_Name: user.last_name || '',
        Join_Date: moment().format('DD/MM/YYYY'),
        Last_Active: moment().format('DD/MM/YYYY HH:mm:ss'),
        Total_Expenses: '0'
      });
    } else {
      existingUser.Last_Active = moment().format('DD/MM/YYYY HH:mm:ss');
      await existingUser.save();
    }
  } catch (error) {
    console.error('Error registering user:', error);
  }
}

async function saveExpenseToSheet(userId, user, session) {
  try {
    const expenseSheet = doc.sheetsByTitle['Expenses'];
    
    const items = [session];
    if (session.additionalItems) {
      items.push(...session.additionalItems);
    }
    
    for (const item of items) {
      await expenseSheet.addRow({
        Date: moment(session.timestamp).format('DD/MM/YYYY'),
        Time: moment(session.timestamp).format('HH:mm:ss'),
        User_ID: userId.toString(),
        Username: user.username || '',
        Item: item.item,
        Amount: item.amount.toString(),
        Location: item.location || session.location || '',
        Category: item.category || session.category,
        Photo_URL: session.photoUrl || '',
        Notes: session.notes || ''
      });
    }
    
    // Update user total expenses
    await updateUserTotalExpenses(userId);
    
  } catch (error) {
    console.error('Error saving expense:', error);
  }
}

async function updateUserTotalExpenses(userId) {
  try {
    const expenseSheet = doc.sheetsByTitle['Expenses'];
    const userSheet = doc.sheetsByTitle['Users'];
    
    const expenseRows = await expenseSheet.getRows();
    const userExpenses = expenseRows.filter(row => row.User_ID === userId.toString());
    
    const total = userExpenses.reduce((sum, row) => sum + parseFloat(row.Amount || 0), 0);
    
    const userRows = await userSheet.getRows();
    const userRow = userRows.find(row => row.User_ID === userId.toString());
    
    if (userRow) {
      userRow.Total_Expenses = total.toString();
      await userRow.save();
    }
  } catch (error) {
    console.error('Error updating user total:', error);
  }
}

async function getTodayExpenseCount(userId) {
  try {
    const expenseSheet = doc.sheetsByTitle['Expenses'];
    const rows = await expenseSheet.getRows();
    
    const today = moment().format('DD/MM/YYYY');
    const todayExpenses = rows.filter(row => 
      row.User_ID === userId.toString() && row.Date === today
    );
    
    return todayExpenses.length;
  } catch (error) {
    return 0;
  }
}

async function getTodayExpenseTotal(userId) {
  try {
    const expenseSheet = doc.sheetsByTitle['Expenses'];
    const rows = await expenseSheet.getRows();
    
    const today = moment().format('DD/MM/YYYY');
    const todayExpenses = rows.filter(row => 
      row.User_ID === userId.toString() && row.Date === today
    );
    
    const total = todayExpenses.reduce((sum, row) => sum + parseFloat(row.Amount || 0), 0);
    return total.toFixed(2);
  } catch (error) {
    return '0.00';
  }
}

async function getWeekExpenseTotal(userId) {
  try {
    const expenseSheet = doc.sheetsByTitle['Expenses'];
    const rows = await expenseSheet.getRows();
    
    const weekStart = moment().startOf('week');
    const weekExpenses = rows.filter(row => {
      if (row.User_ID !== userId.toString()) return false;
      const expenseDate = moment(row.Date, 'DD/MM/YYYY');
      return expenseDate.isSameOrAfter(weekStart);
    });
    
    const total = weekExpenses.reduce((sum, row) => sum + parseFloat(row.Amount || 0), 0);
    return total.toFixed(2);
  } catch (error) {
    return '0.00';
  }
}

async function getMonthExpenseTotal(userId) {
  try {
    const expenseSheet = doc.sheetsByTitle['Expenses'];
    const rows = await expenseSheet.getRows();
    
    const monthStart = moment().startOf('month');
    const monthExpenses = rows.filter(row => {
      if (row.User_ID !== userId.toString()) return false;
      const expenseDate = moment(row.Date, 'DD/MM/YYYY');
      return expenseDate.isSameOrAfter(monthStart);
    });
    
    const total = monthExpenses.reduce((sum, row) => sum + parseFloat(row.Amount || 0), 0);
    return total.toFixed(2);
  } catch (error) {
    return '0.00';
  }
}

async function generateDailyReport(userId) {
  const today = moment().format('DD/MM/YYYY');
  const total = await getTodayExpenseTotal(userId);
  const count = await getTodayExpenseCount(userId);
  
  return `
📊 *Laporan Harian - ${today}*

💰 *Jumlah Belanja:* RM${total}
📝 *Bilangan Transaksi:* ${count}
💳 *Purata setiap transaksi:* RM${count > 0 ? (parseFloat(total) / count).toFixed(2) : '0.00'}

${count === 0 ? '✨ Tiada belanja hari ini! Jimat sekali!' : '💪 Teruskan jejak belanja anda!'}

---
🤖 *Laporan automatik dari LaporanBelanjaBot*
👨‍💻 *Dibangunkan oleh Fadirul Ezwan*
  `;
}

async function generateWeeklyReport(userId) {
  try {
    const expenseSheet = doc.sheetsByTitle['Expenses'];
    const rows = await expenseSheet.getRows();
    
    const weekStart = moment().startOf('week');
    const weekEnd = moment().endOf('week');
    
    const weekExpenses = rows.filter(row => {
      if (row.User_ID !== userId.toString()) return false;
      const expenseDate = moment(row.Date, 'DD/MM/YYYY');
      return expenseDate.isBetween(weekStart, weekEnd, null, '[]');
    });
    
    const total = weekExpenses.reduce((sum, row) => sum + parseFloat(row.Amount || 0), 0);
    const count = weekExpenses.length;
    
    // Group by category
    const categories = {};
    weekExpenses.forEach(row => {
      const category = row.Category || 'Lain-lain';
      categories[category] = (categories[category] || 0) + parseFloat(row.Amount || 0);
    });
    
    // Top category
    const topCategory = Object.entries(categories).reduce((a, b) => a[1] > b[1] ? a : b, ['', 0]);
    
    let categoryBreakdown = '';
    Object.entries(categories).forEach(([cat, amount]) => {
      categoryBreakdown += `• ${cat}: RM${amount.toFixed(2)}\n`;
    });
    
    return `
📊 *Laporan Mingguan*
📅 ${weekStart.format('DD/MM')} - ${weekEnd.format('DD/MM/YYYY')}

💰 *Jumlah Belanja:* RM${total.toFixed(2)}
📝 *Bilangan Transaksi:* ${count}
💳 *Purata harian:* RM${(total / 7).toFixed(2)}
🏆 *Kategori tertinggi:* ${topCategory[0]} (RM${topCategory[1].toFixed(2)})

*Pecahan mengikut kategori:*
${categoryBreakdown}

${count === 0 ? '✨ Minggu yang jimat!' : count > 50 ? '⚠️ Belanja agak tinggi minggu ini' : '👍 Belanja dalam kawalan yang baik'}

---
🤖 *Laporan automatik dari LaporanBelanjaBot*
👨‍💻 *Dibangunkan oleh Fadirul Ezwan*
    `;
  } catch (error) {
    return '❌ Ralat menghasilkan laporan mingguan. Sila cuba lagi.';
  }
}

async function generateMonthlyReport(userId) {
  try {
    const expenseSheet = doc.sheetsByTitle['Expenses'];
    const rows = await expenseSheet.getRows();
    
    const monthStart = moment().startOf('month');
    const monthEnd = moment().endOf('month');
    const currentMonth = moment().format('MMMM YYYY');
    
    const monthExpenses = rows.filter(row => {
      if (row.User_ID !== userId.toString()) return false;
      const expenseDate = moment(row.Date, 'DD/MM/YYYY');
      return expenseDate.isBetween(monthStart, monthEnd, null, '[]');
    });
    
    const total = monthExpenses.reduce((sum, row) => sum + parseFloat(row.Amount || 0), 0);
    const count = monthExpenses.length;
    const daysInMonth = moment().daysInMonth();
    const currentDay = moment().date();
    
    // Group by category
    const categories = {};
    monthExpenses.forEach(row => {
      const category = row.Category || 'Lain-lain';
      categories[category] = (categories[category] || 0) + parseFloat(row.Amount || 0);
    });
    
    // Group by week
    const weeks = {};
    monthExpenses.forEach(row => {
      const week = Math.ceil(moment(row.Date, 'DD/MM/YYYY').date() / 7);
      weeks[`Minggu ${week}`] = (weeks[`Minggu ${week}`] || 0) + parseFloat(row.Amount || 0);
    });
    
    let categoryBreakdown = '';
    Object.entries(categories)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .forEach(([cat, amount]) => {
        categoryBreakdown += `• ${cat}: RM${amount.toFixed(2)}\n`;
      });
    
    let weekBreakdown = '';
    Object.entries(weeks).forEach(([week, amount]) => {
      weekBreakdown += `• ${week}: RM${amount.toFixed(2)}\n`;
    });
    
    const projection = (total / currentDay) * daysInMonth;
    
    return `
📊 *Laporan Bulanan - ${currentMonth}*

💰 *Jumlah Belanja:* RM${total.toFixed(2)}
📝 *Bilangan Transaksi:* ${count}
💳 *Purata harian:* RM${(total / currentDay).toFixed(2)}
📈 *Unjuran bulan penuh:* RM${projection.toFixed(2)}
📊 *Progress:* ${((currentDay / daysInMonth) * 100).toFixed(1)}% bulan berlalu

*Top 5 Kategori:*
${categoryBreakdown}

*Pecahan mingguan:*
${weekBreakdown}

*Analisa:*
${total > 1000 ? '⚠️ Belanja tinggi bulan ini' : total > 500 ? '👍 Belanja sederhana' : '✨ Belanja jimat!'}
${projection > total * 1.5 ? '\n💡 Cadangan: Kurangkan belanja untuk minggu seterusnya' : ''}

---
🤖 *Laporan automatik dari LaporanBelanjaBot*
👨‍💻 *Dibangunkan oleh Fadirul Ezwan*
    `;
  } catch (error) {
    return '❌ Ralat menghasilkan laporan bulanan. Sila cuba lagi.';
  }
}

async function generateAnalysis(userId) {
  try {
    const expenseSheet = doc.sheetsByTitle['Expenses'];
    const rows = await expenseSheet.getRows();
    
    const userExpenses = rows.filter(row => row.User_ID === userId.toString());
    const total = userExpenses.reduce((sum, row) => sum + parseFloat(row.Amount || 0), 0);
    
    // Last 30 days analysis
    const last30Days = moment().subtract(30, 'days');
    const recent = userExpenses.filter(row => {
      const expenseDate = moment(row.Date, 'DD/MM/YYYY');
      return expenseDate.isAfter(last30Days);
    });
    
    const recentTotal = recent.reduce((sum, row) => sum + parseFloat(row.Amount || 0), 0);
    
    // Most expensive single purchase
    const maxExpense = userExpenses.reduce((max, row) => {
      const amount = parseFloat(row.Amount || 0);
      return amount > max.amount ? {amount, item: row.Item, date: row.Date} : max;
    }, {amount: 0, item: '', date: ''});
    
    // Most frequent category
    const categories = {};
    userExpenses.forEach(row => {
      const category = row.Category || 'Lain-lain';
      categories[category] = (categories[category] || 0) + 1;
    });
    
    const topCategory = Object.entries(categories).reduce((a, b) => a[1] > b[1] ? a : b, ['', 0]);
    
    // Most frequent location
    const locations = {};
    userExpenses.forEach(row => {
      if (row.Location) {
        locations[row.Location] = (locations[row.Location] || 0) + 1;
      }
    });
    
    const topLocation = Object.entries(locations).reduce((a, b) => a[1] > b[1] ? a : b, ['', 0]);
    
    return `
🔍 *Analisa Mendalam Belanja Anda*

*Statistik Keseluruhan:*
💰 Jumlah belanja keseluruhan: RM${total.toFixed(2)}
📝 Total transaksi: ${userExpenses.length}
💳 Purata setiap transaksi: RM${(total / userExpenses.length).toFixed(2)}

*30 Hari Terkini:*
💰 Jumlah: RM${recentTotal.toFixed(2)}
📊 Purata harian: RM${(recentTotal / 30).toFixed(2)}
📈 ${recentTotal > (total * 0.5) ? 'Trend meningkat' : 'Trend menurun'}

*Rekod Tertinggi:*
🏆 Pembelian terbesar: ${maxExpense.item} - RM${maxExpense.amount.toFixed(2)}
📅 Tarikh: ${maxExpense.date}

*Pattern Belanja:*
🥇 Kategori kegemaran: ${topCategory[0]} (${topCategory[1]} kali)
📍 Lokasi kerap: ${topLocation[0] || 'Tidak tersedia'} ${topLocation[1] ? `(${topLocation[1]} kali)` : ''}

*Cadangan:*
${recentTotal > 800 ? '💡 Cuba kurangkan belanja harian sebanyak 20%' : ''}
${topCategory[0] === 'Makan & Minum' && topCategory[1] > 20 ? '🍽️ Pertimbangkan masak di rumah lebih kerap' : ''}
${maxExpense.amount > 100 ? '🛒 Buat senarai sebelum membeli untuk elak pembelian impulsif' : ''}

---
🤖 *Analisa automatik dari LaporanBelanjaBot*
👨‍💻 *Dibangunkan oleh Fadirul Ezwan*
    `;
  } catch (error) {
    return '❌ Ralat menghasilkan analisa. Sila cuba lagi.';
  }
}

// Auto-report functions
async function sendDailyReports() {
  try {
    const userSheet = doc.sheetsByTitle['Users'];
    const users = await userSheet.getRows();
    
    for (const user of users) {
      const userId = parseInt(user.User_ID);
      const report = await generateDailyReport(userId);
      
      // Send to both bots' users
      try {
        await bot2.sendMessage(userId, `🌅 *Laporan Harian Automatik*\n\n${report}`, { parse_mode: 'Markdown' });
      } catch (error) {
        console.log(`User ${userId} may have blocked the bot`);
      }
    }
  } catch (error) {
    console.error('Error sending daily reports:', error);
  }
}

async function sendWeeklyReports() {
  try {
    const userSheet = doc.sheetsByTitle['Users'];
    const users = await userSheet.getRows();
    
    for (const user of users) {
      const userId = parseInt(user.User_ID);
      const report = await generateWeeklyReport(userId);
      
      try {
        await bot2.sendMessage(userId, `📅 *Laporan Mingguan Automatik*\n\n${report}`, { parse_mode: 'Markdown' });
      } catch (error) {
        console.log(`User ${userId} may have blocked the bot`);
      }
    }
  } catch (error) {
    console.error('Error sending weekly reports:', error);
  }
}

async function sendMonthlyReports() {
  try {
    const userSheet = doc.sheetsByTitle['Users'];
    const users = await userSheet.getRows();
    
    for (const user of users) {
      const userId = parseInt(user.User_ID);
      const report = await generateMonthlyReport(userId);
      
      try {
        await bot2.sendMessage(userId, `📊 *Laporan Bulanan Automatik*\n\n${report}`, { parse_mode: 'Markdown' });
      } catch (error) {
        console.log(`User ${userId} may have blocked the bot`);
      }
    }
  } catch (error) {
    console.error('Error sending monthly reports:', error);
  }
}

// Setup cron jobs (for local development)
if (process.env.NODE_ENV !== 'production') {
  // Daily reports at 8 PM
  cron.schedule('0 20 * * *', sendDailyReports, {
    timezone: 'Asia/Kuala_Lumpur'
  });
  
  // Weekly reports on Sunday at 8 PM
  cron.schedule('0 20 * * 0', sendWeeklyReports, {
    timezone: 'Asia/Kuala_Lumpur'
  });
  
  // Monthly reports on 1st day at 8 PM
  cron.schedule('0 20 1 * *', sendMonthlyReports, {
    timezone: 'Asia/Kuala_Lumpur'
  });
}

// Express routes
app.get('/', (req, res) => {
  res.json({
    status: 'Bot Tracking Belanja is running!',
    timestamp: moment().format('DD/MM/YYYY HH:mm:ss'),
    bots: {
      bot1: 'LaporBelanjaBot - Input Bot',
      bot2: 'LaporanBelanjaBot - Report Bot'
    },
    developer: 'Fadirul Ezwan'
  });
});

// Webhook endpoints
app.post('/webhook/bot1', (req, res) => {
  bot1.processUpdate(req.body);
  res.sendStatus(200);
});

app.post('/webhook/bot2', (req, res) => {
  bot2.processUpdate(req.body);
  res.sendStatus(200);
});

// Cron endpoints for Vercel
app.get('/api/cron/daily', async (req, res) => {
  await sendDailyReports();
  res.json({ success: true, message: 'Daily reports sent' });
});

app.get('/api/cron/weekly', async (req, res) => {
  await sendWeeklyReports();
  res.json({ success: true, message: 'Weekly reports sent' });
});

app.get('/api/cron/monthly', async (req, res) => {
  await sendMonthlyReports();
  res.json({ success: true, message: 'Monthly reports sent' });
});

// Health check endpoint
app.get('/health', async (req, res) => {
  try {
    await doc.loadInfo();
    res.json({
      status: 'healthy',
      timestamp: moment().format('DD/MM/YYYY HH:mm:ss'),
      sheets: 'connected',
      bots: 'active'
    });
  } catch (error) {
    res.status(500).json({
      status: 'unhealthy',
      error: error.message
    });
  }
});

// Initialize everything
async function initialize() {
  console.log('🚀 Starting Tracking Belanja Bot...');
  
  await initializeSheet();
  setupBot1();
  setupBot2();
  
  console.log('✅ Bot1 (LaporBelanjaBot) initialized');
  console.log('✅ Bot2 (LaporanBelanjaBot) initialized');
  console.log('📊 Google Sheets connected');
  console.log('⏰ Cron jobs scheduled');
  console.log('🌐 Webhooks ready');
  
  const PORT = process.env.PORT || 3000;
  app.listen(PORT, () => {
    console.log(`🌟 Server running on port ${PORT}`);
    console.log(`🔗 Webhook URLs:`);
    console.log(`   Bot1: https://${VERCEL_DOMAIN}/webhook/bot1`);
    console.log(`   Bot2: https://${VERCEL_DOMAIN}/webhook/bot2`);
    console.log('👨‍💻 Developed by Fadirul Ezwan');
  });
}

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error);
});

process.on('unhandledRejection', (error) => {
  console.error('Unhandled Rejection:', error);
});

// Start the application
initialize().catch(console.error);

module.exports = app;