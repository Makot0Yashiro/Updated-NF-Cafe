/* PREVIEW MODE sample data (see api.js). Shapes match the admin JSON API contract.
   The ingredients and recipes are the suggested starter seed for the backend. Delete this file once the backend is live. */
const img = (k, n) => `https://loremflickr.com/480/360/${k}?lock=${n}`;

// Mirrors GROUPS in menu_data.py: group = top-level heading, sort = display order.
const CATEGORIES = [
  {id: 'food', name: 'Food', group: 'Food', color: '#c8553d', emoji: '🍔', sort: 1},
  {id: 'coffee', name: 'Coffee', group: 'Beverages', color: '#8a5a33', emoji: '☕', sort: 2},
  {id: 'icetea', name: 'Ice Tea', group: 'Beverages', color: '#3f8a6b', emoji: '🧋', sort: 3},
  {id: 'floats', name: 'Floats', group: 'Beverages', color: '#b5578a', emoji: '🍨', sort: 4},
];

// [id, name, unit, stock, low_at]
const ING = [
  [1, 'Potatoes', 'g', 8000, 2000], [2, 'Cooking oil', 'ml', 5000, 1000], [3, 'Salt', 'g', 1000, 200],
  [4, 'Tortilla chips', 'g', 3000, 800], [5, 'Cheese sauce', 'ml', 400, 500], [6, 'Burger buns', 'pc', 24, 10],
  [7, 'Beef patties', 'pc', 6, 10], [8, 'Lettuce', 'g', 1500, 300], [9, 'Tomatoes', 'g', 0, 300],
  [10, 'Salad dressing', 'ml', 1200, 300], [11, 'Espresso beans', 'g', 2500, 500], [12, 'Fresh milk', 'ml', 9000, 2000],
  [13, 'Matcha powder', 'g', 600, 150], [14, 'Caramel syrup', 'ml', 800, 200], [15, 'Chocolate syrup', 'ml', 1500, 300],
  [16, 'Cream cookies', 'pc', 40, 20], [17, 'Cherry syrup', 'ml', 700, 200], [18, 'Vanilla ice cream', 'g', 4000, 1000],
  [19, 'Black tea', 'g', 900, 200], [20, 'Ice', 'g', 20000, 5000], [21, 'Sugar syrup', 'ml', 2000, 500],
  [22, 'Paper straws', 'pc', 300, 100],
].map(([id, name, unit, stock, low_at]) => ({id, name, unit, stock, low_at}));
const ING_BY_ID = Object.fromEntries(ING.map(i => [i.id, i]));

// [id, name, cat_id, price, image keywords, recipe [[ingredient_id, qty per serving], ...]]
const ITEMS = [
  ['fries', 'Fries', 'food', 99, 'french,fries', [[1, 200], [2, 30], [3, 2]]],
  ['nachos', 'Nachos', 'food', 149, 'nachos', [[4, 150], [5, 60]]],
  ['burger', 'Burger', 'food', 189, 'burger', [[6, 1], [7, 1], [8, 20], [9, 30]]],
  ['salad', 'Salad', 'food', 139, 'salad', [[8, 120], [9, 60], [10, 30]]],
  ['c-matcha', 'Matcha Latte', 'coffee', 135, 'matcha,latte', [[13, 5], [12, 200], [21, 15]]],
  ['c-latte', 'Coffee Latte', 'coffee', 120, 'latte,coffee', [[11, 18], [12, 200]]],
  ['c-caramel', 'Salted Caramel', 'coffee', 140, 'caramel,coffee', [[11, 18], [12, 180], [14, 30], [3, 1]]],
  ['c-americano', 'Americano', 'coffee', 95, 'americano,coffee', [[11, 18]]],
  ['t-matcha', 'Matcha Iced Tea', 'icetea', 130, 'iced,matcha', [[13, 5], [20, 150], [21, 20], [12, 100], [22, 1]]],
  ['t-oreo', 'Cookies and Cream', 'icetea', 140, 'oreo,milkshake', [[16, 3], [12, 200], [20, 150], [22, 1]]],
  ['t-blackforest', 'Black Forest Iced Tea', 'icetea', 145, 'chocolate,cherry,drink', [[19, 4], [15, 20], [17, 20], [20, 150], [22, 1]]],
  ['t-choco', 'Chocolate Iced Tea', 'icetea', 130, 'iced,chocolate,drink', [[19, 4], [15, 30], [20, 150], [22, 1]]],
  ['f-choco', 'Chocolate Float', 'floats', 150, 'chocolate,float', [[15, 30], [12, 150], [18, 80], [22, 1]]],
  ['f-blackforest', 'Black Forest Float', 'floats', 160, 'icecream,float,cherry', [[15, 20], [17, 20], [18, 80], [12, 150], [22, 1]]],
  ['f-matcha', 'Matcha Float', 'floats', 155, 'matcha,icecream', [[13, 5], [12, 150], [18, 80], [22, 1]]],
].map(([id, name, cat_id, price, kw, recipe], n) => ({
  id, name, cat_id, price, img: img(kw, n + 7), active: id !== 'salad',   // one hidden item so that state is visible
  recipe: recipe.map(([ingredient_id, qty]) => ({ingredient_id, qty, name: ING_BY_ID[ingredient_id].name, unit: ING_BY_ID[ingredient_id].unit})),
}));

/** Same shape as GET /admin/api/ingredients */
export function ingredients() {
  return ING.map(i => ({...i, used_in: ITEMS.filter(it => it.recipe.some(r => r.ingredient_id === i.id)).map(it => it.name)}));
}

/** Same shape as GET /admin/api/menu-items */
export function menuItems() {
  return {categories: CATEGORIES, items: ITEMS, ingredients: ING.map(({id, name, unit, stock}) => ({id, name, unit, stock}))};
}
